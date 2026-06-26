import uuid
from fastapi import APIRouter, UploadFile, File, Depends
from app.api.dependencies import require_valid_session
from app.services.file_service import store_upload_file, parse_matlab_metadata
from app.services.session_service import update_session_field
from app.utils.helpers import utcnow

router = APIRouter(prefix="/upload", tags=["Upload"])

MATLAB_KEYS = ["ecg_signal", "filtered_signal", "rpeaks", "beat_segments"]


@router.post("/matlab")
async def upload_matlab(
    ecg_signal: UploadFile = File(...),
    filtered_signal: UploadFile = File(...),
    rpeaks: UploadFile = File(...),
    beat_segments: UploadFile = File(...),
    session: dict = Depends(require_valid_session),
):
    """Upload the 4 MATLAB CSV output files."""
    session_id = session["_id"]
    upload_id = str(uuid.uuid4())

    files_map = {
        "ecg_signal": ecg_signal,
        "filtered_signal": filtered_signal,
        "rpeaks": rpeaks,
        "beat_segments": beat_segments,
    }

    stored = {}
    for key, file in files_map.items():
        meta = await store_upload_file(session_id, "uploads", file, key, validate_csv=True)
        stored[key] = meta

    # Parse metadata from the stored files
    metadata = parse_matlab_metadata(stored)

    upload_doc = {
        "upload_id": upload_id,
        "files": stored,
        "metadata": metadata,
        "uploaded_at": utcnow().isoformat(),
    }
    await update_session_field(session_id, "matlab_upload", upload_doc)

    # ── Critical: wipe stale downstream pipeline results ──────────────────────
    # Any previous inference/quantization/hex results from an earlier dataset
    # MUST be cleared so the UI doesn't show old data for the new upload.
    await update_session_field(session_id, "inference", None)
    await update_session_field(session_id, "quantization", None)
    await update_session_field(session_id, "hex_generation", None)
    await update_session_field(session_id, "fpga_analysis", None)
    await update_session_field(session_id, "vivado_upload", None)
    await update_session_field(session_id, "fpga_metrics", None)

    # Invalidate Redis dashboard cache so the frontend gets fresh data immediately
    try:
        from app.database.redis_client import get_redis
        redis = get_redis()
        if redis:
            await redis.delete(f"dashboard:{session_id}")
            await redis.delete(f"inference_results:{session_id}")
    except Exception:
        pass  # Redis unavailable is fine — in-memory session is already clean

    return {
        "upload_id": upload_id,
        "session_id": session_id,
        "status": "uploaded",
        "files": {
            k: {
                "filename": v["filename"],
                "size_bytes": v["size_bytes"],
                "storage_path": v["storage_path"],
            }
            for k, v in stored.items()
        },
        "metadata": metadata,
        "uploaded_at": upload_doc["uploaded_at"],
        "next_step": "Start inference by calling POST /api/v1/inference/start",
    }


@router.post("/demo")
async def load_demo_data(session: dict = Depends(require_valid_session)):
    """Automatically load generated sample patient ECG data into the session."""
    import os
    from app.storage.minio_client import upload_bytes
    from app.utils.helpers import s3_path
    
    session_id = session["_id"]
    upload_id = str(uuid.uuid4())
    
    # Path to test_data folder
    test_data_dir = "test_data"
    test_files = {
        "ecg_signal": "ecg_signal.csv",
        "filtered_signal": "filtered_signal.csv",
        "rpeaks": "rpeaks.csv",
        "beat_segments": "beat_segments.csv",
    }
    
    # Check if test files exist, generate if missing
    if not os.path.exists(test_data_dir) or not all(os.path.exists(os.path.join(test_data_dir, f)) for f in test_files.values()):
        os.makedirs(test_data_dir, exist_ok=True)
        try:
            from scripts.generate_sample_data import generate
            generate(test_data_dir, 30 * 360, 360)
        except Exception as e:
            # Fallback in case of import/path issue - create dummy data files
            import pandas as pd
            import numpy as np
            # Generate minimal dummy data
            t = np.linspace(0, 30, 30 * 360)
            pd.DataFrame({"time": t, "amplitude": np.sin(t)}).to_csv(os.path.join(test_data_dir, "ecg_signal.csv"), index=False)
            pd.DataFrame({"time": t, "amplitude": np.sin(t)}).to_csv(os.path.join(test_data_dir, "filtered_signal.csv"), index=False)
            pd.DataFrame({"peak_index": [360, 720, 1080], "peak_time": [1.0, 2.0, 3.0]}).to_csv(os.path.join(test_data_dir, "rpeaks.csv"), index=False)
            pd.DataFrame(np.zeros((3, 200)), columns=[f"sample_{i}" for i in range(200)]).to_csv(os.path.join(test_data_dir, "beat_segments.csv"), index=False)

    stored = {}
    for key, filename in test_files.items():
        filepath = os.path.join(test_data_dir, filename)
        with open(filepath, "rb") as f:
            content = f.read()
            
        obj_name = s3_path(session_id, "uploads", filename)
        storage_path = upload_bytes(obj_name, content, "text/plain")
        
        stored[key] = {
            "filename": filename,
            "size_bytes": len(content),
            "storage_path": storage_path,
            "object_name": obj_name,
        }

    metadata = parse_matlab_metadata(stored)

    upload_doc = {
        "upload_id": upload_id,
        "files": stored,
        "metadata": metadata,
        "uploaded_at": utcnow().isoformat(),
    }
    await update_session_field(session_id, "matlab_upload", upload_doc)

    return {
        "upload_id": upload_id,
        "session_id": session_id,
        "status": "uploaded",
        "files": {
            k: {
                "filename": v["filename"],
                "size_bytes": v["size_bytes"],
                "storage_path": v["storage_path"],
            }
            for k, v in stored.items()
        },
        "metadata": metadata,
        "uploaded_at": upload_doc["uploaded_at"],
        "next_step": "Start inference by calling POST /api/v1/inference/start",
    }

