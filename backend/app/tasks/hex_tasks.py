import logging
import pymongo

from app.tasks.celery_app import celery_app
from app.services.quantization_service import quantize_model
from app.services.hex_generator import generate_hex_files
from app.config import settings
from app.utils.helpers import utcnow

logger = logging.getLogger(__name__)


def _get_sync_db():
    client = pymongo.MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
    return client[settings.MONGODB_DB]


def _broadcast(session_id: str, payload: dict):
    try:
        import redis as sync_redis, json
        r = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.publish(f"ws:{session_id}", json.dumps(payload))
    except Exception as e:
        logger.warning(f"Broadcast failed: {e}")


@celery_app.task(bind=True, name="tasks.run_quantization")
def run_quantization_task(self, session_id: str):
    db = _get_sync_db()
    try:
        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {"quantization.status": "processing"}},
        )
        _broadcast(session_id, {"type": "quantization_progress", "message": "Quantizing FP32 → INT8..."})

        result = quantize_model()

        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {
                "quantization.status": "completed",
                "quantization.original_size_mb": result["original_size_mb"],
                "quantization.quantized_size_mb": result["quantized_size_mb"],
                "quantization.compression_ratio": result["compression_ratio"],
                "quantization.accuracy_fp32": result["accuracy_fp32"],
                "quantization.accuracy_int8": result["accuracy_int8"],
                "quantization.accuracy_drop": result["accuracy_drop"],
                "quantization.completed_at": utcnow(),
            }},
        )
        _broadcast(session_id, {"type": "quantization_complete", "result": result})
        return {"status": "completed", **result}

    except Exception as exc:
        logger.error(f"Quantization task failed: {exc}")
        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {"quantization.status": "failed", "quantization.error": str(exc)}},
        )
        _broadcast(session_id, {"type": "quantization_failed", "error": str(exc)})
        raise


@celery_app.task(bind=True, name="tasks.run_hex_generation")
def run_hex_generation_task(self, session_id: str):
    db = _get_sync_db()
    try:
        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {"hex_generation.status": "processing"}},
        )
        _broadcast(session_id, {"type": "hex_generation_progress", "progress": 10, "message": "Extracting weights..."})

        result = generate_hex_files(session_id)

        _broadcast(session_id, {"type": "hex_generation_progress", "progress": 90, "message": "Packaging ZIP..."})

        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {
                "hex_generation.status": "completed",
                "hex_generation.files": result["files"],
                "hex_generation.archive": result["archive"],
                "hex_generation.memory_map": result["memory_map"],
                "hex_generation.generated_at": utcnow(),
            }},
        )
        _broadcast(session_id, {"type": "hex_generation_complete", "download_url": result["archive"]["download_url"]})
        return {"status": "completed", "file_count": len(result["files"])}

    except Exception as exc:
        logger.error(f"HEX generation task failed: {exc}")
        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {"hex_generation.status": "failed", "hex_generation.error": str(exc)}},
        )
        _broadcast(session_id, {"type": "hex_generation_failed", "error": str(exc)})
        raise


@celery_app.task(bind=True, name="tasks.run_fpga_analysis")
def run_fpga_analysis_task(self, session_id: str, power_obj: str, timing_obj: str, util_obj: str):
    from app.storage.minio_client import download_bytes
    from app.services.fpga_parser import parse_all_reports

    db = _get_sync_db()
    try:
        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {"fpga_analysis.status": "processing"}},
        )
        _broadcast(session_id, {"type": "fpga_analysis_progress", "message": "Parsing Vivado reports..."})

        power_content = download_bytes(power_obj).decode("utf-8", errors="ignore")
        timing_content = download_bytes(timing_obj).decode("utf-8", errors="ignore")
        util_content = download_bytes(util_obj).decode("utf-8", errors="ignore")

        metrics = parse_all_reports(power_content, timing_content, util_content)

        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {
                "fpga_analysis.status": "completed",
                "fpga_analysis.metrics": metrics,
                "fpga_analysis.parsed_at": utcnow(),
            }},
        )
        _broadcast(session_id, {"type": "fpga_analysis_complete", "message": "Hardware analysis complete. Dashboard ready."})
        return {"status": "completed"}

    except Exception as exc:
        logger.error(f"FPGA analysis task failed: {exc}")
        db.sessions.update_one(
            {"_id": session_id},
            {"$set": {"fpga_analysis.status": "failed", "fpga_analysis.error": str(exc)}},
        )
        _broadcast(session_id, {"type": "fpga_analysis_failed", "error": str(exc)})
        raise
