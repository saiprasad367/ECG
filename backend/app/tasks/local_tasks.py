import logging
import asyncio
from datetime import datetime

from app.ml.predictor import extract_beats_from_csv, run_inference_on_beats, compute_summary
from app.services.quantization_service import quantize_model
from app.services.hex_generator import generate_hex_files
from app.storage.minio_client import download_bytes, upload_bytes
from app.utils.helpers import utcnow
from app.services.session_service import update_session_field, get_session
from app.api.routes.websocket import broadcast_to_session

logger = logging.getLogger(__name__)


async def _broadcast(session_id: str, payload: dict):
    """Directly send updates to registered WebSockets (no Redis network overhead!)."""
    try:
        await broadcast_to_session(session_id, payload)
    except Exception as e:
        logger.warning(f"Local broadcast failed: {e}")


async def run_inference_task(session_id: str, beat_segments_obj: str):
    started = utcnow()
    try:
        # Update status → processing
        await update_session_field(session_id, "inference.status", "processing")
        await update_session_field(session_id, "inference.progress", 0)
        await update_session_field(session_id, "inference.started_at", started.isoformat())
        await _broadcast(session_id, {"type": "inference_progress", "progress": 0, "message": "Loading model..."})

        # Load beat bytes and parse
        beat_bytes = download_bytes(beat_segments_obj)
        beats = extract_beats_from_csv(beat_bytes)
        total = len(beats)

        if total == 0:
            raise ValueError("No beats found in beat_segments file")

        await _broadcast(session_id, {"type": "inference_progress", "progress": 5, "message": f"Analyzing {total} beats..."})

        # Run inference in a separate threadpool to keep the FastAPI main loop 100% responsive
        loop = asyncio.get_event_loop()
        
        def on_progress(pct, current, total_b):
            asyncio.run_coroutine_threadsafe(
                _broadcast(session_id, {
                    "type": "inference_progress",
                    "progress": pct,
                    "current_beat": current,
                    "total_beats": total_b,
                    "message": f"Analyzing beat {current} of {total_b}...",
                }),
                loop
            )

        predictions = await loop.run_in_executor(
            None, 
            lambda: run_inference_on_beats(beats, progress_callback=on_progress)
        )
        summary = compute_summary(predictions)
        completed = utcnow()
        ms = int((completed - started).total_seconds() * 1000)

        # Save results to session
        await update_session_field(session_id, "inference.status", "completed")
        await update_session_field(session_id, "inference.progress", 100)
        await update_session_field(session_id, "inference.predictions", predictions)
        await update_session_field(session_id, "inference.summary", summary)
        await update_session_field(session_id, "inference.metrics", {
            "average_confidence": summary["average_confidence"],
            "low_confidence_count": summary["low_confidence_count"],
            "high_confidence_count": summary["high_confidence_count"],
        })
        await update_session_field(session_id, "inference.completed_at", completed.isoformat())
        await update_session_field(session_id, "inference.processing_time_ms", ms)
        
        # Mark progress as ready
        await update_session_field(session_id, "progress.ai_inference", True)

        await _broadcast(session_id, {
            "type": "inference_complete",
            "job_id": "local-job",
            "processing_time_seconds": round(ms / 1000, 1),
            "summary": summary,
        })
    except Exception as exc:
        logger.error(f"Local inference task failed: {exc}", exc_info=True)
        await update_session_field(session_id, "inference.status", "failed")
        await update_session_field(session_id, "inference.error", str(exc))
        await _broadcast(session_id, {"type": "inference_failed", "error": str(exc)})


async def run_quantization_task(session_id: str):
    try:
        await update_session_field(session_id, "quantization.status", "processing")
        await _broadcast(session_id, {"type": "quantization_progress", "message": "Quantizing FP32 → INT8..."})

        # Run model quantization in a separate thread
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, quantize_model)

        await update_session_field(session_id, "quantization.status", "completed")
        await update_session_field(session_id, "quantization.original_size_mb", result["original_size_mb"])
        await update_session_field(session_id, "quantization.quantized_size_mb", result["quantized_size_mb"])
        await update_session_field(session_id, "quantization.compression_ratio", result["compression_ratio"])
        await update_session_field(session_id, "quantization.accuracy_fp32", result["accuracy_fp32"])
        await update_session_field(session_id, "quantization.accuracy_int8", result["accuracy_int8"])
        await update_session_field(session_id, "quantization.accuracy_drop", result["accuracy_drop"])
        await update_session_field(session_id, "quantization.completed_at", utcnow().isoformat())
        
        await update_session_field(session_id, "progress.quantization", True)

        await _broadcast(session_id, {"type": "quantization_complete", "result": result})
    except Exception as exc:
        logger.error(f"Local quantization task failed: {exc}", exc_info=True)
        await update_session_field(session_id, "quantization.status", "failed")
        await update_session_field(session_id, "quantization.error", str(exc))
        await _broadcast(session_id, {"type": "quantization_failed", "error": str(exc)})


async def run_hex_generation_task(session_id: str):
    try:
        await update_session_field(session_id, "hex_generation.status", "processing")
        await _broadcast(session_id, {"type": "hex_generation_progress", "progress": 10, "message": "Extracting weights..."})

        # Run FPGA weight HEX extraction in a separate thread
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: generate_hex_files(session_id))

        await _broadcast(session_id, {"type": "hex_generation_progress", "progress": 90, "message": "Packaging ZIP..."})

        await update_session_field(session_id, "hex_generation.status", "completed")
        await update_session_field(session_id, "hex_generation.files", result["files"])
        await update_session_field(session_id, "hex_generation.archive", result["archive"])
        await update_session_field(session_id, "hex_generation.memory_map", result["memory_map"])
        await update_session_field(session_id, "hex_generation.generated_at", utcnow().isoformat())
        
        await update_session_field(session_id, "progress.hex_generation", True)

        await _broadcast(session_id, {"type": "hex_generation_complete", "download_url": result["archive"]["download_url"]})
    except Exception as exc:
        logger.error(f"Local HEX generation task failed: {exc}", exc_info=True)
        await update_session_field(session_id, "hex_generation.status", "failed")
        await update_session_field(session_id, "hex_generation.error", str(exc))
        await _broadcast(session_id, {"type": "hex_generation_failed", "error": str(exc)})


async def run_fpga_analysis_task(session_id: str, power_obj: str, timing_obj: str, util_obj: str):
    from app.services.fpga_parser import parse_all_reports
    try:
        await update_session_field(session_id, "fpga_analysis.status", "processing")
        await _broadcast(session_id, {"type": "fpga_analysis_progress", "message": "Parsing Vivado reports..."})

        power_content = download_bytes(power_obj).decode("utf-8", errors="ignore")
        timing_content = download_bytes(timing_obj).decode("utf-8", errors="ignore")
        util_content = download_bytes(util_obj).decode("utf-8", errors="ignore")

        # Run heavy text parsing in separate thread
        loop = asyncio.get_event_loop()
        metrics = await loop.run_in_executor(
            None,
            lambda: parse_all_reports(power_content, timing_content, util_content)
        )

        await update_session_field(session_id, "fpga_analysis.status", "completed")
        await update_session_field(session_id, "fpga_analysis.metrics", metrics)
        await update_session_field(session_id, "fpga_analysis.parsed_at", utcnow().isoformat())

        # Also populate "fpga_metrics" directly on the session root so the frontend is 100% happy!
        await update_session_field(session_id, "fpga_metrics", metrics)
        await update_session_field(session_id, "progress.fpga_analysis", True)

        await _broadcast(session_id, {"type": "fpga_analysis_complete", "message": "Hardware analysis complete. Dashboard ready."})
    except Exception as exc:
        logger.error(f"Local FPGA analysis task failed: {exc}", exc_info=True)
        await update_session_field(session_id, "fpga_analysis.status", "failed")
        await update_session_field(session_id, "fpga_analysis.error", str(exc))
        await _broadcast(session_id, {"type": "fpga_analysis_failed", "error": str(exc)})
