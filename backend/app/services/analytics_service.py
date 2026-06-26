import json
import logging
from typing import Dict, Any

from app.database.mongodb import get_db
from app.database.redis_client import get_redis
from app.storage.minio_client import get_presigned_url
from app.ml.model_config import get_real_metrics, get_training_history

logger = logging.getLogger(__name__)


async def get_dashboard_data(session_id: str) -> Dict[str, Any]:
    from app.services.session_service import get_session
    redis = get_redis()

    # Try cache first (short 30s TTL so real-time data stays fresh)
    if redis:
        cached = await redis.get(f"dashboard:{session_id}")
        if cached:
            return json.loads(cached)

    try:
        session = await get_session(session_id)
    except Exception:
        return {}

    if not session:
        return {}

    # ── Progress flags ─────────────────────────────────────────────────────────
    progress = {
        "matlab_upload": session.get("matlab_upload") is not None,
        "inference": (session.get("inference") or {}).get("status") == "completed",
        "inference_status": (session.get("inference") or {}).get("status"),
        "quantization": (session.get("quantization") or {}).get("status") == "completed",
        "quantization_status": (session.get("quantization") or {}).get("status"),
        "hex_generation": (session.get("hex_generation") or {}).get("status") == "completed",
        "hex_status": (session.get("hex_generation") or {}).get("status"),
        "fpga_upload": session.get("vivado_upload") is not None,
        "fpga_analysis": (session.get("fpga_analysis") or {}).get("status") == "completed",
    }

    # ── ECG data (from actual uploaded files) ─────────────────────────────────
    ecg_data = {}
    if session.get("matlab_upload"):
        meta = session["matlab_upload"].get("metadata", {})
        files = session["matlab_upload"].get("files", {})
        ecg_data = {
            "total_beats": meta.get("total_beats", 0),
            "duration_seconds": meta.get("duration_seconds", 0),
            "sampling_rate": meta.get("sampling_rate", 360),
            "signal_quality": meta.get("signal_quality", "unknown"),
        }
        for k, v in files.items():
            obj = v.get("object_name", "")
            if obj:
                ecg_data[f"{k}_url"] = get_presigned_url(obj)

    # ── AI inference results (from actual CNN predictions) ────────────────────
    ai_results = {}
    inf = session.get("inference") or {}
    if inf.get("status") == "completed":
        summary = inf.get("summary", {})
        total = summary.get("total_beats", 1)
        ai_results = {
            "summary": {
                "total_beats": summary.get("total_beats", 0),
                "class_distribution": summary.get("class_distribution", {}),
                "abnormal_count": summary.get("abnormal_count", 0),
                "abnormal_beats": summary.get("abnormal_count", 0),  # alias
                "abnormal_percentage": summary.get("abnormal_percentage", 0),
                "average_confidence": summary.get("average_confidence", None),
                "low_confidence_count": summary.get("low_confidence_count", 0),
                "high_confidence_count": summary.get("high_confidence_count", 0),
            },
            "metrics": {
                # average_confidence is the live runtime metric (NOT training accuracy)
                "average_confidence": summary.get("average_confidence", None),
                "processing_time_ms": inf.get("processing_time_ms"),
                "completed_at": inf.get("completed_at"),
            },
        }

    # ── Real training metrics from generated/metrics.json ────────────────────
    real_training_metrics = get_real_metrics()  # {} if model not trained yet
    training_history = get_training_history()   # [] if no history

    # ── Quantization results ──────────────────────────────────────────────────
    quant = session.get("quantization") or {}
    quant_results = {}
    if quant.get("status") == "completed":
        quant_results = {k: v for k, v in quant.items() if k not in ("status", "job_id", "task_id", "started_at")}

    # ── FPGA metrics (from parsed Vivado reports) ─────────────────────────────
    fpga_metrics_raw = session.get("fpga_analysis") or {}
    fpga_summary = {}
    if fpga_metrics_raw.get("status") == "completed":
        metrics = fpga_metrics_raw.get("metrics", {})
        power = metrics.get("power_analysis", {})
        timing = metrics.get("timing_analysis", {})
        util = metrics.get("utilization", {})
        perf = metrics.get("performance", {})
        fpga_summary = {
            "power_mw": power.get("total_power_mw"),
            "dynamic_power_mw": power.get("dynamic_power_mw"),
            "static_power_mw": power.get("static_power_mw"),
            "frequency_mhz": timing.get("clock_frequency_mhz"),
            "clock_period_ns": timing.get("clock_period_ns"),
            "worst_negative_slack_ns": timing.get("worst_negative_slack_ns"),
            "latency_us": perf.get("latency_us"),
            "latency_cycles": perf.get("latency_cycles"),
            "throughput_beats_per_second": perf.get("throughput_beats_per_second"),
            "timing_met": timing.get("timing_met", False),
            "failing_endpoints": timing.get("failing_endpoints", 0),
            "utilization": {
                "lut_percentage": (util.get("lut") or {}).get("percentage"),
                "ff_percentage": (util.get("flip_flops") or {}).get("percentage"),
                "bram_percentage": (util.get("bram_tile") or {}).get("percentage"),
                "dsp_percentage": (util.get("dsp") or {}).get("percentage"),
                "lut_used": (util.get("lut") or {}).get("used"),
                "lut_available": (util.get("lut") or {}).get("available"),
                "ff_used": (util.get("flip_flops") or {}).get("used"),
                "bram_used": (util.get("bram_tile") or {}).get("used"),
                "dsp_used": (util.get("dsp") or {}).get("used"),
            },
            "device_info": metrics.get("device_info", {}),
        }

    # ── Hardware comparison: only from real FPGA + estimates ─────────────────
    # Only populate when FPGA analysis is done (real measured data)
    comparison = {}
    if fpga_summary:
        fpga_latency = fpga_summary.get("latency_us")
        fpga_power = fpga_summary.get("power_mw")
        fpga_throughput = fpga_summary.get("throughput_beats_per_second")
        comparison = {
            "hardware_platforms": {
                "fpga": {
                    "latency_us": fpga_latency,
                    "power_mw": fpga_power,
                    "throughput_beats_per_sec": fpga_throughput,
                    "source": "vivado_report",
                },
                # CPU/GPU are estimates based on known hardware benchmarks for 1D-CNN inference
                "cpu_estimate": {
                    "latency_us": round((fpga_latency or 1.52) * 29.6, 1) if fpga_latency else None,
                    "power_mw": 15000,  # Typical Xeon processor power at inference
                    "throughput_beats_per_sec": round(1_000_000 / (((fpga_latency or 1.52) * 29.6) * 1000), 0) if fpga_latency else None,
                    "source": "estimated_29.6x_slower_than_fpga",
                },
                "gpu_estimate": {
                    "latency_us": round((fpga_latency or 1.52) * 1.64, 1) if fpga_latency else None,
                    "power_mw": 75000,  # Typical NVIDIA GPU TDP
                    "throughput_beats_per_sec": round(1_000_000 / (((fpga_latency or 1.52) * 1.64) * 1000), 0) if fpga_latency else None,
                    "source": "estimated_1.64x_slower_than_fpga",
                },
            }
        }

    # ── HEX generation ────────────────────────────────────────────────────────
    hex_data = session.get("hex_generation") or {}
    download_links = {}
    if hex_data.get("archive", {}).get("object_name"):
        download_links["hex_files_zip"] = get_presigned_url(hex_data["archive"]["object_name"])

    dashboard = {
        "session_id": session_id,
        "session_status": session.get("status", "active"),
        "last_updated": str(session.get("last_activity", "")),
        "progress": progress,
        "ecg_data": ecg_data,
        "ai_results": ai_results,
        "quantization_results": quant_results,
        "fpga_metrics": fpga_summary,
        "model_metrics": real_training_metrics,      # Real training metrics (or {} if untrained)
        "training_history": training_history,        # Real epoch history (or [] if untrained)
        "hex_generation_results": {
            "files": hex_data.get("files", []),
            "memory_map": hex_data.get("memory_map", {}),
            "formats_generated": hex_data.get("formats_generated", []),
        },
        "comparison": comparison,
        "download_links": download_links,
    }

    # Cache for 30s (short TTL so inference progress updates are visible quickly)
    if redis:
        await redis.setex(f"dashboard:{session_id}", 30, json.dumps(dashboard, default=str))

    return dashboard
