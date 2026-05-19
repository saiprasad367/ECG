import asyncio
import logging
from datetime import datetime

import pymongo

from app.tasks.celery_app import celery_app
from app.ml.predictor import extract_beats_from_csv, run_inference_on_beats, compute_summary
from app.storage.minio_client import download_bytes, upload_bytes
from app.config import settings
from app.utils.helpers import utcnow, s3_path

logger = logging.getLogger(__name__)


def _get_sync_db():
    """Get a synchronous MongoDB client for use inside Celery tasks."""
    client = pymongo.MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    return client[settings.MONGODB_DB]


def _broadcast(session_id: str, payload: dict):
    """Push a WebSocket message via Redis pub/sub."""
    try:
        import redis as sync_redis
        import json
        r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.publish(f"ws:{session_id}", json.dumps(payload))
    except Exception as e:
        logger.warning(f"Broadcast failed: {e}")


@celery_app.task(bind=True, name="tasks.run_inference")
def run_inference_task(self, session_id: str, beat_segments_obj: str):
    db = _get_sync_db()
    started = utcnow()

    try:
        # Update status → processing
        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {"inference.status": "processing", "inference.started_at": started}},
        )
        _broadcast(session_id, {"type": "inference_progress", "progress": 0, "message": "Loading model..."})

        # Download beat segments
        beat_bytes = download_bytes(beat_segments_obj)
        beats = extract_beats_from_csv(beat_bytes)
        total = len(beats)

        if total == 0:
            raise ValueError("No beats found in beat_segments file")

        _broadcast(session_id, {"type": "inference_progress", "progress": 5, "message": f"Analyzing {total} beats..."})

        # Progress callback
        def on_progress(pct, current, total_b):
            self.update_state(state="PROGRESS", meta={"progress": pct, "current_beat": current, "total_beats": total_b})
            _broadcast(session_id, {
                "type": "inference_progress",
                "progress": pct,
                "current_beat": current,
                "total_beats": total_b,
                "message": f"Analyzing beat {current} of {total_b}...",
            })

        predictions = run_inference_on_beats(beats, progress_callback=on_progress)
        summary = compute_summary(predictions)
        completed = utcnow()
        ms = int((completed - started).total_seconds() * 1000)

        # Save results
        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {
                "inference.status": "completed",
                "inference.progress": 100,
                "inference.predictions": predictions,
                "inference.summary": summary,
                "inference.metrics": {
                    "average_confidence": summary["average_confidence"],
                    "low_confidence_count": summary["low_confidence_count"],
                    "high_confidence_count": summary["high_confidence_count"],
                },
                "inference.completed_at": completed,
                "inference.processing_time_ms": ms,
            }},
        )

        _broadcast(session_id, {
            "type": "inference_complete",
            "job_id": self.request.id,
            "processing_time_seconds": round(ms / 1000, 1),
            "summary": summary,
        })

        return {"status": "completed", "total_beats": total, "processing_ms": ms}

    except Exception as exc:
        logger.error(f"Inference task failed for session {session_id}: {exc}")
        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {"inference.status": "failed", "inference.error": str(exc)}},
        )
        _broadcast(session_id, {"type": "inference_failed", "error": str(exc)})
        raise
