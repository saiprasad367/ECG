from fastapi import Header, Request, HTTPException
from app.services.session_service import get_or_raise_session


async def get_session_id(x_session_id: str = Header(..., alias="X-Session-ID")) -> str:
    """Extract and validate session ID from request header."""
    if not x_session_id or len(x_session_id) < 10:
        raise HTTPException(status_code=400, detail="Invalid or missing X-Session-ID header")
    return x_session_id


async def require_valid_session(x_session_id: str = Header(..., alias="X-Session-ID")) -> dict:
    """Dependency that fetches & extends the session, raising if missing/expired."""
    session = await get_or_raise_session(x_session_id)
    return session
