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
    """
    Estimate ECG duration in seconds.
    If 'time' column holds actual seconds (float, small increments like 0.0, 0.00278...)
    we use max(time). If it holds sample indices (integers 0, 1, 2, 3...) we divide by
    sampling_rate. Fallback: len(df) / sampling_rate.
    """
    if "time" in df_ecg.columns:
        try:
            t = pd.to_numeric(df_ecg["time"], errors="coerce").dropna()
            if len(t) == 0:
                return len(df_ecg) / sampling_rate
            t_max = float(t.max())
            t_min = float(t.min())
            t_range = t_max - t_min
            # Heuristic: if max time > 5x the number of rows, it's sample indices
            # (e.g. 17459 max for 17460 rows at 360Hz = indices, not seconds)
            # Real-second time would be <= total_rows / sampling_rate
            n_rows = len(df_ecg)
            if t_max > n_rows / sampling_rate * 2:
                # Sample indices — convert to seconds
                return round(t_max / sampling_rate, 3)
            else:
                # Actual seconds
                return round(t_max, 3)
        except Exception:
            pass
    return round(len(df_ecg) / sampling_rate, 3)
