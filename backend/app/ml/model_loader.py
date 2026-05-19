import torch
import os
import logging
from app.ml.model_config import ECGClassifier
from app.config import settings

logger = logging.getLogger(__name__)

_model: ECGClassifier = None
_device: torch.device = None


def get_device() -> torch.device:
    global _device
    if _device is None:
        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return _device


def load_model(model_path: str = None) -> ECGClassifier:
    global _model
    if _model is not None:
        return _model

    path = model_path or settings.MODEL_PATH
    device = get_device()
    model = ECGClassifier()

    if not os.path.exists(path):
        logger.error(f"❌ Model file not found at '{path}'. You must train the model first.")
        raise FileNotFoundError(f"Model file not found at '{path}'. No mock weights allowed.")

    try:
        state_dict = torch.load(path, map_location=device, weights_only=True)
        model.load_state_dict(state_dict)
        logger.info(f"✅ Model loaded from {path} on {device}")
    except Exception as e:
        logger.error(f"❌ Could not load weights from {path}: {e}")
        raise RuntimeError(f"Failed to load model weights: {e}")

    model.to(device)
    model.eval()
    _model = model
    return _model


def unload_model():
    global _model
    _model = None


def get_model() -> ECGClassifier:
    global _model
    if _model is None:
        return load_model()
    return _model


def model_is_loaded() -> bool:
    return _model is not None or os.path.exists(settings.MODEL_PATH)
