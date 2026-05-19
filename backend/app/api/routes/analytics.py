from fastapi import APIRouter, Depends
from app.api.dependencies import require_valid_session
from app.services.analytics_service import get_dashboard_data

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/dashboard")
async def dashboard(session: dict = Depends(require_valid_session)):
    """Single endpoint returning all data needed for the complete frontend dashboard."""
    session_id = session["_id"]
    data = await get_dashboard_data(session_id)
    return data
