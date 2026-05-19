from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from typing import Optional
from app.services.session_service import create_session, update_session_field
from app.api.dependencies import require_valid_session
from app.utils.helpers import utcnow
from datetime import timedelta
from app.config import settings

router = APIRouter(prefix="/session", tags=["Session"])


class InitRequest(BaseModel):
    client_info: Optional[dict] = {}


@router.post("/init")
async def init_session(body: InitRequest, request: Request):
    """Create a new analysis session."""
    client_info = {
        "ip_address": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", ""),
        **(body.client_info or {}),
    }
    session = await create_session(client_info)
    return {
        "session_id": session["_id"],
        "expires_at": session["expires_at"].isoformat() + "Z",
        "status": session["status"],
    }


@router.post("/reset")
async def reset_session(session: dict = Depends(require_valid_session)):
    """Reset the session analysis states back to empty."""
    session_id = session["_id"]
    fields_to_reset = [
        "matlab_upload",
        "vivado_upload",
        "inference",
        "quantization",
        "hex_generation",
        "fpga_analysis",
    ]
    for field in fields_to_reset:
        await update_session_field(session_id, field, None)
    
    return {"status": "reset", "session_id": session_id}

