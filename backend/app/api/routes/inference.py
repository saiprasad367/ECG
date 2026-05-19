import uuid
import json
import csv
import io
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.api.dependencies import require_valid_session
from app.services.session_service import update_session_field
from app.tasks.local_tasks import run_inference_task
from app.utils.helpers import utcnow
from app.utils.exceptions import NoFilesUploadedError, InferenceNotCompleteError, TaskAlreadyRunningError
from app.database.redis_client import get_redis
from app.ml.model_config import MODEL_CONFIG

router = APIRouter(prefix="/inference", tags=["Inference"])


class InferenceStartRequest(BaseModel):
    model_version: Optional[str] = "v1.0.0"
    options: Optional[dict] = {}


@router.post("/start")
async def start_inference(
    body: InferenceStartRequest,
    background_tasks: BackgroundTasks,
    session: dict = Depends(require_valid_session),
):
    session_id = session["_id"]

    if not session.get("matlab_upload"):
        raise NoFilesUploadedError()

    # Prevent duplicate runs
    inf = session.get("inference") or {}
    if inf.get("status") in ("queued", "processing"):
        started_at_str = inf.get("started_at")
        is_stale = False
        if started_at_str:
            try:
                from datetime import datetime
                started_at_naive = datetime.fromisoformat(started_at_str).replace(tzinfo=None)
                if (utcnow() - started_at_naive).total_seconds() > 60:
                    is_stale = True
            except Exception:
                is_stale = True
        else:
            is_stale = True

        if not is_stale:
            raise TaskAlreadyRunningError("inference")

    job_id = str(uuid.uuid4())
    beat_obj = session["matlab_upload"]["files"]["beat_segments"]["object_name"]

    # Queue local background task
    background_tasks.add_task(run_inference_task, session_id, beat_obj)

    await update_session_field(session_id, "inference", {
        "job_id": job_id,
        "task_id": job_id,
        "status": "queued",
        "progress": 0,
        "started_at": utcnow().isoformat(),
    })

    return {
        "job_id": job_id,
        "session_id": session_id,
        "status": "queued",
        "message": "Inference job queued. Connect to WebSocket for real-time updates.",
        "websocket_url": f"/ws/session/{session_id}",
        "estimated_time_seconds": 60,
        "started_at": utcnow().isoformat(),
    }


@router.get("/status")
async def inference_status(session: dict = Depends(require_valid_session)):
    inf = session.get("inference") or {}
    if not inf:
        return {"status": "not_started", "progress": 0}

    return {
        "job_id": inf.get("job_id"),
        "status": inf.get("status", "unknown"),
        "progress": inf.get("progress", 0),
        "message": inf.get("message", ""),
        "started_at": inf.get("started_at"),
        "completed_at": inf.get("completed_at"),
        "processing_time_ms": inf.get("processing_time_ms"),
    }


@router.get("/results")
async def inference_results(session: dict = Depends(require_valid_session)):
    session_id = session["_id"]
    inf = session.get("inference") or {}

    if inf.get("status") != "completed":
        raise InferenceNotCompleteError()

    # Try Redis cache first
    redis = get_redis()
    if redis:
        cached = await redis.get(f"inference_results:{session_id}")
        if cached:
            return json.loads(cached)

    result = {
        "session_id": session_id,
        "job_id": inf.get("job_id"),
        "status": "completed",
        "completed_at": inf.get("completed_at"),
        "summary": inf.get("summary", {}),
        "predictions": inf.get("predictions", []),
        "metrics": inf.get("metrics", {}),
        "model_info": MODEL_CONFIG,
    }

    # Cache for 24h
    if redis:
        await redis.setex(
            f"inference_results:{session_id}",
            86400,
            json.dumps(result, default=str),
        )

    return result


@router.get("/download/csv")
async def download_predictions_csv(session: dict = Depends(require_valid_session)):
    inf = session.get("inference") or {}
    if inf.get("status") != "completed":
        raise InferenceNotCompleteError()

    predictions = inf.get("predictions", [])
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "beat_index", "beat_time_seconds", "class", "confidence",
        "prob_Normal", "prob_Ventricular", "prob_Supraventricular", "prob_Fusion", "prob_Unknown",
        "is_abnormal", "alert_level",
    ])
    writer.writeheader()
    for p in predictions:
        probs = p.get("probabilities", {})
        writer.writerow({
            "beat_index": p["beat_index"],
            "beat_time_seconds": p["beat_time_seconds"],
            "class": p["class"],
            "confidence": p["confidence"],
            "prob_Normal": probs.get("Normal", 0),
            "prob_Ventricular": probs.get("Ventricular", 0),
            "prob_Supraventricular": probs.get("Supraventricular", 0),
            "prob_Fusion": probs.get("Fusion", 0),
            "prob_Unknown": probs.get("Unknown", 0),
            "is_abnormal": p.get("is_abnormal", False),
            "alert_level": p.get("alert_level", ""),
        })

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=predictions.csv"},
    )
