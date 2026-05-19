import uuid
from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks
from app.api.dependencies import require_valid_session
from app.services.file_service import store_upload_file
from app.services.session_service import update_session_field
from app.tasks.local_tasks import run_fpga_analysis_task
from app.utils.helpers import utcnow

router = APIRouter(prefix="/fpga", tags=["FPGA"])


@router.post("/upload")
async def upload_vivado_reports(
    background_tasks: BackgroundTasks,
    power_report: UploadFile = File(...),
    timing_report: UploadFile = File(...),
    utilization_report: UploadFile = File(...),
    session: dict = Depends(require_valid_session),
):
    """Upload Vivado synthesis reports and trigger automated parsing."""
    session_id = session["_id"]
    upload_id = str(uuid.uuid4())

    files_map = {
        "power": power_report,
        "timing": timing_report,
        "utilization": utilization_report,
    }

    stored = {}
    for key, file in files_map.items():
        meta = await store_upload_file(session_id, "fpga_reports", file, key, validate_csv=False)
        stored[key] = meta

    upload_doc = {
        "upload_id": upload_id,
        "files": stored,
        "uploaded_at": utcnow().isoformat(),
    }
    await update_session_field(session_id, "vivado_upload", upload_doc)
    await update_session_field(session_id, "fpga_analysis", {
        "job_id": str(uuid.uuid4()),
        "status": "queued",
    })

    # Trigger background parsing
    background_tasks.add_task(
        run_fpga_analysis_task,
        session_id,
        stored["power"]["object_name"],
        stored["timing"]["object_name"],
        stored["utilization"]["object_name"],
    )

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
        "uploaded_at": upload_doc["uploaded_at"],
        "next_step": "Analysis will start automatically. Check status at GET /api/v1/fpga/status",
    }


@router.get("/status")
async def fpga_status(session: dict = Depends(require_valid_session)):
    fpga = session.get("fpga_analysis") or {}
    return {
        "job_id": fpga.get("job_id"),
        "status": fpga.get("status", "not_started"),
    }


@router.get("/results")
async def fpga_results(session: dict = Depends(require_valid_session)):
    fpga = session.get("fpga_analysis") or {}
    if fpga.get("status") != "completed":
        return {"status": fpga.get("status", "not_started"), "message": "Analysis not yet complete"}

    metrics = fpga.get("metrics", {})
    return {
        "session_id": session["_id"],
        "job_id": fpga.get("job_id"),
        "status": "completed",
        "parsed_at": fpga.get("parsed_at"),
        **metrics,
    }
