"""
model.py
API route exposing real training metrics and history for the frontend.
"""
from fastapi import APIRouter
from app.ml.model_config import get_real_metrics, get_training_history, MODEL_CONFIG
from app.ml.model_loader import model_is_loaded
import os

router = APIRouter(prefix="/model", tags=["Model"])


@router.get("/metrics")
async def model_metrics():
    """
    Return real training accuracy, F1, precision, recall from generated/metrics.json.
    Returns an empty object if the model has not been trained yet (no fake data).
    """
    real = get_real_metrics()
    history = get_training_history()

    return {
        "architecture": MODEL_CONFIG,
        "trained": bool(real),   # False if model weights exist but metrics.json doesn't
        "model_loaded": model_is_loaded(),
        "training_metrics": real if real else None,
        "training_history": history if history else None,
        "note": (
            "Training metrics loaded from generated/metrics.json" if real
            else "No training metrics found. Run scripts/train_model.py to generate real metrics."
        ),
    }


@router.get("/status")
async def model_status():
    """Return model loading status and architecture details."""
    from app.config import settings
    fp32_exists = os.path.exists(settings.MODEL_PATH)
    quantized_exists = os.path.exists(settings.QUANTIZED_MODEL_PATH)
    metrics_exist = bool(get_real_metrics())
    history_exists = bool(get_training_history())

    return {
        "fp32_model_exists": fp32_exists,
        "quantized_model_exists": quantized_exists,
        "training_metrics_available": metrics_exist,
        "training_history_available": history_exists,
        "model_path": settings.MODEL_PATH,
        "quantized_model_path": settings.QUANTIZED_MODEL_PATH,
        "architecture": MODEL_CONFIG,
        "ready_for_inference": fp32_exists,
    }
