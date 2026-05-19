from datetime import datetime, timedelta
from typing import Optional, Dict
import uuid
import logging
from threading import Lock

from app.config import settings
from app.utils.helpers import utcnow
from app.utils.exceptions import SessionNotFoundError

logger = logging.getLogger(__name__)

# Core in-memory database storage
_sessions: Dict[str, dict] = {}
_lock = Lock()


def _new_session_doc(session_id: str, client_info: dict) -> dict:
    now = utcnow()
    expires = now + timedelta(hours=settings.SESSION_TTL_HOURS)
    return {
        "_id": session_id,
        "created_at": now,
        "last_activity": now,
        "expires_at": expires,
        "status": "active",
        "client_info": client_info,
        "matlab_upload": None,
        "vivado_upload": None,
        "inference": None,
        "quantization": None,
        "hex_generation": None,
        "fpga_analysis": None,
    }


async def create_session(client_info: dict) -> dict:
    session_id = str(uuid.uuid4())
    doc = _new_session_doc(session_id, client_info)
    with _lock:
        _sessions[session_id] = doc
    logger.info(f"Created in-memory session: {session_id}")
    return doc


async def get_session(session_id: str) -> dict:
    with _lock:
        doc = _sessions.get(session_id)
        if not doc:
            # Resilient auto-creation to match database resilience
            try:
                uuid.UUID(session_id)
                doc = _new_session_doc(session_id, {"ip_address": "auto-created", "user_agent": "auto-created"})
                _sessions[session_id] = doc
                logger.info(f"Resiliently auto-created session: {session_id}")
            except ValueError:
                raise SessionNotFoundError(session_id)

        if doc.get("expires_at") and doc["expires_at"] < utcnow():
            # Auto-renew expired session
            now = utcnow()
            expires = now + timedelta(hours=settings.SESSION_TTL_HOURS)
            doc["last_activity"] = now
            doc["expires_at"] = expires
            doc["status"] = "active"

        return doc


async def extend_session(session_id: str):
    new_expiry = utcnow() + timedelta(hours=settings.SESSION_TTL_HOURS)
    with _lock:
        if session_id in _sessions:
            _sessions[session_id]["last_activity"] = utcnow()
            _sessions[session_id]["expires_at"] = new_expiry


async def update_session_field(session_id: str, field: str, value):
    with _lock:
        if session_id in _sessions:
            # Support dotted nested updates, e.g. "inference.status"
            if "." in field:
                parts = field.split(".")
                parent = _sessions[session_id]
                for p in parts[:-1]:
                    if parent.get(p) is None:
                        parent[p] = {}
                    # Ensure parent is a dict
                    if not isinstance(parent[p], dict):
                        parent[p] = {}
                    parent = parent[p]
                parent[parts[-1]] = value
            else:
                _sessions[session_id][field] = value
            _sessions[session_id]["last_activity"] = utcnow()


async def get_or_raise_session(session_id: str) -> dict:
    session = await get_session(session_id)
    await extend_session(session_id)
    return session


async def delete_expired_sessions() -> int:
    now = utcnow()
    deleted = 0
    with _lock:
        for sid, doc in list(_sessions.items()):
            if doc.get("expires_at") and doc["expires_at"] < now:
                del _sessions[sid]
                deleted += 1
    return deleted
