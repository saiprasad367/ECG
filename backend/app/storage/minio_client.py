import os
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# Base storage path relative to backend root directory
STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "storage"))


def get_minio_client():
    return None


async def ensure_bucket():
    """Ensure the local storage directory exists."""
    os.makedirs(STORAGE_DIR, exist_ok=True)
    logger.info(f"⚡ Local File Storage initialized at: {STORAGE_DIR}")


def upload_bytes(object_name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Save bytes to local disk."""
    # Ensure relative subdirectories exist
    clean_obj_name = object_name.replace("s3://", "").replace(f"{settings.MINIO_BUCKET}/", "")
    target_path = os.path.join(STORAGE_DIR, clean_obj_name.replace("/", os.sep))
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    
    with open(target_path, "wb") as f:
        f.write(data)
        
    logger.info(f"💾 File uploaded to local storage: {clean_obj_name}")
    return f"s3://{settings.MINIO_BUCKET}/{clean_obj_name}"


def download_bytes(object_name: str) -> bytes:
    """Read bytes from local disk."""
    clean_obj_name = object_name.replace("s3://", "").replace(f"{settings.MINIO_BUCKET}/", "").replace("local://", "")
    target_path = os.path.join(STORAGE_DIR, clean_obj_name.replace("/", os.sep))
    
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Local storage file not found: {target_path}")
        
    with open(target_path, "rb") as f:
        return f.read()


def get_presigned_url(object_name: str, expires_hours: int = 24) -> str:
    """Return a direct download route handled by our FastAPI backend proxy."""
    clean_obj_name = object_name.replace("s3://", "").replace(f"{settings.MINIO_BUCKET}/", "").replace("local://", "")
    return f"http://127.0.0.1:8000/api/v1/download/direct?object_name={clean_obj_name}"



def delete_prefix(prefix: str):
    """Delete all local files under a specific prefix path."""
    import shutil
    clean_prefix = prefix.replace("s3://", "").replace(f"{settings.MINIO_BUCKET}/", "")
    target_dir = os.path.join(STORAGE_DIR, clean_prefix.replace("/", os.sep))
    
    if os.path.exists(target_dir):
        if os.path.isdir(target_dir):
            shutil.rmtree(target_dir)
        else:
            os.remove(target_dir)
        logger.info(f"🗑️ Deleted local storage path: {clean_prefix}")


def object_exists(object_name: str) -> bool:
    """Check if file exists locally."""
    clean_obj_name = object_name.replace("s3://", "").replace(f"{settings.MINIO_BUCKET}/", "").replace("local://", "")
    target_path = os.path.join(STORAGE_DIR, clean_obj_name.replace("/", os.sep))
    return os.path.exists(target_path)
