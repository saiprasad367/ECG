import io
import logging
import pandas as pd
from fastapi import UploadFile

from app.storage.minio_client import upload_bytes, download_bytes, get_presigned_url, object_exists
from app.utils.helpers import s3_path
from app.utils.validators import (
    validate_file_size, validate_csv_extension, validate_rpt_extension,
    validate_csv_content, count_beats_from_segments, estimate_duration,
)
from app.utils.exceptions import InvalidFileTypeError

logger = logging.getLogger(__name__)


async def store_upload_file(
    session_id: str,
    subfolder: str,
    file: UploadFile,
    file_key: str,
    validate_csv: bool = True,
) -> dict:
    content = await file.read()
    filename = file.filename or file_key

    validate_file_size(filename, len(content))

    if validate_csv:
        validate_csv_extension(filename)
        validate_csv_content(filename, content, file_key)
    else:
        validate_rpt_extension(filename)

    obj_name = s3_path(session_id, subfolder, filename)
    storage_path = upload_bytes(obj_name, content, "text/plain")

    return {
        "filename": filename,
        "size_bytes": len(content),
        "storage_path": storage_path,
        "object_name": obj_name,
    }


def load_csv_from_storage(object_name: str) -> pd.DataFrame:
    content = download_bytes(object_name)
    return pd.read_csv(io.BytesIO(content))


def load_bytes_from_storage(object_name: str) -> bytes:
    return download_bytes(object_name)


def get_download_url(object_name: str) -> str:
    return get_presigned_url(object_name)


def parse_matlab_metadata(files_meta: dict) -> dict:
    """Extract total_beats, duration, sampling_rate from uploaded file metadata."""
    try:
        # Load beat segments to count beats
        beat_obj = files_meta.get("beat_segments", {}).get("object_name")
        if beat_obj:
            content = download_bytes(beat_obj)
            df = pd.read_csv(io.BytesIO(content))
            numeric_cols = df.select_dtypes(include=["number"]).columns
            if len(numeric_cols) >= 10:
                total_beats = len(df)
            else:
                # long format
                id_col = next((c for c in df.columns if c.lower() in ["beat_id", "beat_index", "index"]), None)
                total_beats = df[id_col].nunique() if id_col else len(df)
        else:
            total_beats = 0

        ecg_obj = files_meta.get("ecg_signal", {}).get("object_name")
        if ecg_obj:
            content = download_bytes(ecg_obj)
            df_ecg = pd.read_csv(io.BytesIO(content))
            duration = estimate_duration(df_ecg)
        else:
            duration = total_beats * 0.8

        return {
            "total_beats": total_beats,
            "duration_seconds": round(duration, 2),
            "sampling_rate": 360,
            "signal_quality": "good",
        }
    except Exception as e:
        logger.warning(f"Could not parse metadata: {e}")
        return {"total_beats": 0, "duration_seconds": 0, "sampling_rate": 360, "signal_quality": "unknown"}
