import json
import logging
from typing import Dict, Any

from app.database.mongodb import get_db
from app.database.redis_client import get_redis
from app.storage.minio_client import get_presigned_url

logger = logging.getLogger(__name__)


async def get_dashboard_data(session_id: str) -> Dict[str, Any]:
    from app.services.session_service import get_session
    redis = get_redis()

    # Try cache first
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

    # Progress flags
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

    # ECG data
    ecg_data = {}
    if session.get("matlab_upload"):
        meta = session["matlab_upload"].get("metadata", {})
        files = session["matlab_upload"].get("files", {})
        ecg_data = {
            "total_beats": meta.get("total_beats", 0),
            "duration_seconds": meta.get("duration_seconds", 0),
            "sampling_rate": meta.get("sampling_rate", 360),
        }
        for k, v in files.items():
            obj = v.get("object_name", "")
            if obj:
                ecg_data[f"{k}_url"] = get_presigned_url(obj)

    # AI results
    ai_results = {}
    inf = session.get("inference") or {}
    if inf.get("status") == "completed":
        ai_results = {
            "summary": inf.get("summary", {}),
            "metrics": inf.get("metrics", {}),
        }

    # Quantization
    quant = session.get("quantization") or {}
    quant_results = {}
    if quant.get("status") == "completed":
        quant_results = {k: v for k, v in quant.items() if k not in ("status", "job_id")}

    # FPGA
    fpga_metrics_raw = session.get("fpga_analysis") or {}
    fpga_summary = {}
    if fpga_metrics_raw.get("status") == "completed":
        metrics = fpga_metrics_raw.get("metrics", {})
        power = metrics.get("power_analysis", {})
        timing = metrics.get("timing_analysis", {})
        util = metrics.get("utilization", {})
        fpga_summary = {
            "power_mw": power.get("total_power_mw"),
            "frequency_mhz": timing.get("clock_frequency_mhz"),
            "latency_us": metrics.get("performance", {}).get("latency_us"),
            "timing_met": timing.get("timing_met", False),
            "utilization": {
                "lut_percentage": (util.get("lut") or {}).get("percentage"),
                "ff_percentage": (util.get("flip_flops") or {}).get("percentage"),
                "bram_percentage": (util.get("bram_tile") or {}).get("percentage"),
                "dsp_percentage": (util.get("dsp") or {}).get("percentage"),
            },
        }

    # HEX download
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
        "hex_generation_results": {
            "files": hex_data.get("files", []),
            "memory_map": hex_data.get("memory_map", {})
        },
        "comparison": {
            "hardware_platforms": {
                "fpga": {"latency_us": 1.52, "power_mw": 4230, "throughput_beats_per_sec": 6578, "efficiency_score": 95},
                "cpu_estimate": {"latency_us": 45.0, "power_mw": 15000, "throughput_beats_per_sec": 222, "efficiency_score": 25},
                "gpu_estimate": {"latency_us": 2.5, "power_mw": 75000, "throughput_beats_per_sec": 4000, "efficiency_score": 40},
            }
        },
        "download_links": download_links,
    }

    # Cache for 60s
    if redis:
        await redis.setex(f"dashboard:{session_id}", 60, json.dumps(dashboard, default=str))

    return dashboard
