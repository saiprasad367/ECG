import uuid
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.api.dependencies import require_valid_session
from app.services.session_service import update_session_field
from app.tasks.local_tasks import run_quantization_task, run_hex_generation_task
from app.utils.helpers import utcnow
from app.utils.exceptions import TaskAlreadyRunningError
from app.storage.minio_client import download_bytes

router = APIRouter(prefix="/quantization", tags=["Quantization"])
hex_router = APIRouter(prefix="/hex", tags=["HEX"])


@router.post("/start")
async def start_quantization(
    background_tasks: BackgroundTasks,
    session: dict = Depends(require_valid_session)
):
    session_id = session["_id"]
    q = session.get("quantization") or {}
    if q.get("status") in ("processing",):
        started_at_str = q.get("started_at")
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
            raise TaskAlreadyRunningError("quantization")

    job_id = str(uuid.uuid4())
    
    # Queue local background task
    background_tasks.add_task(run_quantization_task, session_id)

    await update_session_field(session_id, "quantization", {
        "job_id": job_id,
        "task_id": job_id,
        "status": "processing",
        "started_at": utcnow().isoformat(),
    })

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Quantizing model from FP32 to INT8...",
        "estimated_time_seconds": 30,
    }


@router.get("/results")
async def quantization_results(session: dict = Depends(require_valid_session)):
    q = session.get("quantization") or {}
    return {
        "job_id": q.get("job_id"),
        "status": q.get("status", "not_started"),
        "original_size_mb": q.get("original_size_mb"),
        "quantized_size_mb": q.get("quantized_size_mb"),
        "compression_ratio": q.get("compression_ratio"),
        "accuracy_fp32": q.get("accuracy_fp32"),
        "accuracy_int8": q.get("accuracy_int8"),
        "accuracy_drop": q.get("accuracy_drop"),
        "completed_at": q.get("completed_at"),
    }


@hex_router.post("/generate")
async def generate_hex(
    background_tasks: BackgroundTasks,
    session: dict = Depends(require_valid_session)
):
    session_id = session["_id"]
    h = session.get("hex_generation") or {}
    if h.get("status") in ("processing",):
        started_at_str = h.get("started_at")
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
            raise TaskAlreadyRunningError("hex generation")

    job_id = str(uuid.uuid4())
    
    # Queue local background task
    background_tasks.add_task(run_hex_generation_task, session_id)

    await update_session_field(session_id, "hex_generation", {
        "job_id": job_id,
        "task_id": job_id,
        "status": "processing",
        "started_at": utcnow().isoformat(),
    })

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Generating HEX files for FPGA deployment...",
        "estimated_time_seconds": 20,
    }


@hex_router.get("/results")
async def hex_results(session: dict = Depends(require_valid_session)):
    h = session.get("hex_generation") or {}
    return {
        "job_id": h.get("job_id"),
        "status": h.get("status", "not_started"),
        "files": h.get("files", []),
        "archive": h.get("archive"),
        "memory_map": h.get("memory_map"),
        "generated_at": h.get("generated_at"),
    }


@hex_router.get("/download")
async def download_hex(session: dict = Depends(require_valid_session)):
    h = session.get("hex_generation") or {}
    archive = h.get("archive") or {}
    obj_name = archive.get("object_name")
    if not obj_name:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="HEX files not yet generated")

    data = download_bytes(obj_name)
    return StreamingResponse(
        iter([data]),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=fpga_weights.zip"},
    )


# Download proxy endpoint
download_router = APIRouter(prefix="/download", tags=["Download"])

@download_router.get("/direct")
async def download_direct(object_name: str = Query(...)):
    try:
        data = download_bytes(object_name)
        content_type = "application/octet-stream"
        if object_name.endswith(".zip"):
            content_type = "application/zip"
        elif object_name.endswith(".csv"):
            content_type = "text/csv"
        return StreamingResponse(
            iter([data]),
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={object_name.split('/')[-1]}"},
        )
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"File not found: {str(e)}")
