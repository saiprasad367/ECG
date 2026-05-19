import uuid
from datetime import datetime, timezone


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ms_elapsed(start: datetime) -> int:
    return int((utcnow() - start).total_seconds() * 1000)


def format_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def s3_path(session_id: str, subfolder: str, filename: str) -> str:
    return f"sessions/{session_id}/{subfolder}/{filename}"


CLASS_NAMES = {0: "Normal", 1: "Ventricular", 2: "Supraventricular", 3: "Fusion", 4: "Unknown"}
CLASS_IDS = {v: k for k, v in CLASS_NAMES.items()}
ABNORMAL_CLASSES = {"Ventricular", "Supraventricular", "Fusion", "Unknown"}


def class_id_to_name(class_id: int) -> str:
    return CLASS_NAMES.get(class_id, "Unknown")


def is_abnormal(class_name: str) -> bool:
    return class_name in ABNORMAL_CLASSES


def alert_level(class_name: str, confidence: float) -> str:
    if class_name == "Normal":
        return None
    if class_name == "Ventricular" and confidence > 0.8:
        return "critical"
    if class_name in ABNORMAL_CLASSES:
        return "warning"
    return "info"
