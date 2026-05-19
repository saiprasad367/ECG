import pandas as pd
import io
from app.utils.exceptions import InvalidFileTypeError, FileTooLargeError, MissingColumnsError

MAX_FILE_SIZE_MB = 100
ALLOWED_CSV_EXTENSIONS = {".csv"}
ALLOWED_RPT_EXTENSIONS = {".rpt", ".txt"}

MATLAB_FILE_SCHEMAS = {
    "ecg_signal": {"required": ["time", "amplitude"], "alt": [["sample", "value"]]},
    "filtered_signal": {"required": ["time", "amplitude"], "alt": [["sample", "value"]]},
    "rpeaks": {"required": [], "any_of": ["peak_index", "index", "sample", "time", "peak_time"]},
    "beat_segments": {"required": [], "any_of": ["beat_id", "beat_index", "index", "segment"]},
}


def validate_file_size(filename: str, size_bytes: int, max_mb: int = MAX_FILE_SIZE_MB):
    if size_bytes > max_mb * 1024 * 1024:
        raise FileTooLargeError(filename, max_mb)


def validate_csv_extension(filename: str):
    import os
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_CSV_EXTENSIONS:
        raise InvalidFileTypeError(filename, ".csv")


def validate_rpt_extension(filename: str):
    import os
    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_RPT_EXTENSIONS:
        raise InvalidFileTypeError(filename, ".rpt")


def validate_csv_content(filename: str, content: bytes, file_key: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(io.BytesIO(content))
    except Exception:
        raise InvalidFileTypeError(filename, "valid CSV")

    schema = MATLAB_FILE_SCHEMAS.get(file_key, {})
    cols_lower = [c.lower().strip() for c in df.columns]

    required = schema.get("required", [])
    missing = [r for r in required if r not in cols_lower]
    if missing:
        # Try to rename columns if there's only 2 and required has 2
        if len(df.columns) == 2 and len(required) == 2:
            df.columns = required
        else:
            raise MissingColumnsError(filename, missing)

    any_of = schema.get("any_of", [])
    if any_of and not any(col in cols_lower for col in any_of):
        # Accept any CSV with numeric data as beat/rpeak file
        pass

    return df


def count_beats_from_segments(df: pd.DataFrame) -> int:
    return len(df)


def estimate_duration(df_ecg: pd.DataFrame, sampling_rate: int = 360) -> float:
    if "time" in df_ecg.columns:
        try:
            return float(df_ecg["time"].max())
        except Exception:
            pass
    return len(df_ecg) / sampling_rate
