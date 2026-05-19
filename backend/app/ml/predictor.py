import torch
import torch.nn.functional as F
import numpy as np
import pandas as pd
import io
import logging
from typing import List, Dict, Any

from app.ml.model_loader import get_model, get_device
from app.ml.model_config import MODEL_CONFIG
from app.utils.helpers import class_id_to_name, is_abnormal, alert_level

logger = logging.getLogger(__name__)

BEAT_LEN = 200  # samples per beat


def preprocess_beat(beat_array: np.ndarray) -> torch.Tensor:
    """Z-score normalize a single beat and convert to tensor."""
    beat = beat_array.astype(np.float32)
    mean = beat.mean()
    std = beat.std() + 1e-8
    beat = (beat - mean) / std

    # Resize/pad to exactly BEAT_LEN samples
    if len(beat) < BEAT_LEN:
        beat = np.pad(beat, (0, BEAT_LEN - len(beat)), mode="edge")
    elif len(beat) > BEAT_LEN:
        beat = beat[:BEAT_LEN]

    # Shape: [1, 1, BEAT_LEN]
    return torch.tensor(beat, dtype=torch.float32).unsqueeze(0).unsqueeze(0)


def extract_beats_from_csv(content: bytes) -> List[np.ndarray]:
    """
    Parse beat_segments CSV into a list of numpy arrays.
    Handles wide format (each row = one beat, columns = samples)
    and long format (beat_id + amplitude columns).
    """
    df = pd.read_csv(io.BytesIO(content))
    cols = [c.lower() for c in df.columns]

    # Wide format: rows=beats, columns=sample_0, sample_1, ...
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if len(numeric_cols) >= 10:
        beats = []
        for _, row in df[numeric_cols].iterrows():
            beats.append(row.values.astype(np.float32))
        return beats

    # Long format: group by beat_id
    id_col = next((c for c in df.columns if c.lower() in ["beat_id", "beat_index", "index"]), None)
    amp_col = next((c for c in df.columns if c.lower() in ["amplitude", "value", "signal"]), None)

    if id_col and amp_col:
        beats = []
        for _, group in df.groupby(id_col):
            beats.append(group[amp_col].values.astype(np.float32))
        return beats

    # Fallback: treat each row as a sample, chunk into BEAT_LEN blocks
    vals = df.iloc[:, -1].values.astype(np.float32)
    beats = [vals[i : i + BEAT_LEN] for i in range(0, len(vals), BEAT_LEN) if len(vals[i : i + BEAT_LEN]) >= 10]
    return beats


def run_inference_on_beats(
    beats: List[np.ndarray],
    progress_callback=None,
) -> List[Dict[str, Any]]:
    """Run CNN inference on a list of beat arrays."""
    model = get_model()
    device = get_device()
    model.eval()

    predictions = []
    class_names = MODEL_CONFIG["class_names"]
    total = len(beats)

    with torch.no_grad():
        for idx, beat in enumerate(beats):
            tensor = preprocess_beat(beat).to(device)
            logits = model(tensor)
            probs = F.softmax(logits, dim=1).squeeze(0).cpu().numpy()

            pred_id = int(np.argmax(probs))
            pred_class = class_id_to_name(pred_id)
            confidence = float(probs[pred_id])

            prob_dict = {class_names[i]: float(probs[i]) for i in range(len(class_names))}
            abnormal = is_abnormal(pred_class)

            predictions.append(
                {
                    "beat_index": idx,
                    "beat_time_seconds": round(idx * 0.8, 3),  # ~75bpm approx
                    "class": pred_class,
                    "class_id": pred_id,
                    "confidence": round(confidence, 4),
                    "probabilities": {k: round(v, 4) for k, v in prob_dict.items()},
                    "is_abnormal": abnormal,
                    "alert_level": alert_level(pred_class, confidence),
                }
            )

            if progress_callback and idx % 10 == 0:
                pct = int((idx + 1) / total * 100)
                progress_callback(pct, idx + 1, total)

    return predictions


def compute_summary(predictions: List[Dict]) -> Dict[str, Any]:
    from collections import Counter
    class_counts = Counter(p["class"] for p in predictions)
    total = len(predictions)
    abnormal_count = sum(1 for p in predictions if p["is_abnormal"])
    avg_confidence = round(sum(p["confidence"] for p in predictions) / total, 4) if total else 0
    low_conf = sum(1 for p in predictions if p["confidence"] < 0.7)

    return {
        "total_beats": total,
        "class_distribution": dict(class_counts),
        "abnormal_count": abnormal_count,
        "abnormal_percentage": round(abnormal_count / total * 100, 2) if total else 0,
        "average_confidence": avg_confidence,
        "low_confidence_count": low_conf,
        "high_confidence_count": total - low_conf,
    }
