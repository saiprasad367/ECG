"""
evaluate_model.py
Evaluates the trained 1D-CNN on the held-out test set and saves:
  models/evaluation/confusion_matrix.json
  models/evaluation/classification_report.json
  models/evaluation/roc_curves.json
  models/evaluation/per_class_metrics.json

Run from backend/ directory:
  python scripts/evaluate_model.py --mitbih datasets/mit-bih
"""

import os
import sys
import json
import logging
import argparse

import numpy as np
import torch
import torch.nn.functional as F

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.model_config import ECGClassifier
from scripts.dataset_loader import get_dataloaders

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CLASS_NAMES = ["Normal", "Ventricular", "Supraventricular", "Fusion", "Unknown"]


def evaluate(mitbih_dir: str, model_path: str = "models/best_model.pth", batch_size: int = 64):
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model not found: {model_path}. Train the model first.")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Evaluating on device: {device}")

    # Load model
    model = ECGClassifier().to(device)
    state = torch.load(model_path, map_location=device, weights_only=True)
    model.load_state_dict(state)
    model.eval()

    # Load test data (ptb_dir empty = skip)
    _, test_loader, _ = get_dataloaders(mitbih_dir, "", batch_size)

    all_labels = []
    all_preds = []
    all_probs = []

    with torch.no_grad():
        for inputs, targets in test_loader:
            inputs = inputs.to(device)
            logits = model(inputs)
            probs = F.softmax(logits, dim=1).cpu().numpy()
            preds = np.argmax(probs, axis=1)

            all_probs.extend(probs.tolist())
            all_preds.extend(preds.tolist())
            all_labels.extend(targets.numpy().tolist())

    all_labels = np.array(all_labels)
    all_preds = np.array(all_preds)
    all_probs = np.array(all_probs)

    # Overall accuracy
    accuracy = float(np.mean(all_labels == all_preds))
    logger.info(f"Overall accuracy: {accuracy:.4f}")

    # Confusion matrix
    num_classes = len(CLASS_NAMES)
    cm = np.zeros((num_classes, num_classes), dtype=int)
    for true, pred in zip(all_labels, all_preds):
        if 0 <= true < num_classes and 0 <= pred < num_classes:
            cm[true][pred] += 1

    cm_dict = {
        "matrix": cm.tolist(),
        "class_names": CLASS_NAMES,
        "overall_accuracy": round(accuracy, 4),
    }

    # Per-class metrics
    per_class = {}
    for i, name in enumerate(CLASS_NAMES):
        tp = int(cm[i, i])
        fp = int(cm[:, i].sum() - tp)
        fn = int(cm[i, :].sum() - tp)
        tn = int(cm.sum() - tp - fp - fn)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        support = int(cm[i, :].sum())

        per_class[name] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "specificity": round(specificity, 4),
            "support": support,
        }
        logger.info(f"  {name}: P={precision:.3f} R={recall:.3f} F1={f1:.3f} (n={support})")

    # Weighted F1
    total = len(all_labels)
    weighted_f1 = sum(
        per_class[n]["f1_score"] * per_class[n]["support"] / total
        for n in CLASS_NAMES if total > 0
    )

    report = {
        "overall_accuracy": round(accuracy, 4),
        "weighted_f1_score": round(weighted_f1, 4),
        "per_class": per_class,
    }

    # ROC curves (One-vs-Rest)
    try:
        from sklearn.metrics import roc_curve, auc
        from sklearn.preprocessing import label_binarize

        y_bin = label_binarize(all_labels, classes=list(range(num_classes)))
        roc_data = {}
        for i, name in enumerate(CLASS_NAMES):
            if y_bin[:, i].sum() == 0:
                continue
            fpr, tpr, _ = roc_curve(y_bin[:, i], all_probs[:, i])
            roc_auc = auc(fpr, tpr)
            # Downsample to 50 points for JSON size
            idx = np.linspace(0, len(fpr) - 1, min(50, len(fpr)), dtype=int)
            roc_data[name] = {
                "fpr": [round(float(x), 4) for x in fpr[idx]],
                "tpr": [round(float(x), 4) for x in tpr[idx]],
                "auc": round(float(roc_auc), 4),
            }
            logger.info(f"  ROC AUC {name}: {roc_auc:.4f}")
    except ImportError:
        logger.warning("sklearn not available, skipping ROC curves")
        roc_data = {}

    # Save outputs
    out_dir = "models/evaluation"
    os.makedirs(out_dir, exist_ok=True)

    with open(f"{out_dir}/confusion_matrix.json", "w") as f:
        json.dump(cm_dict, f, indent=2)

    with open(f"{out_dir}/classification_report.json", "w") as f:
        json.dump(report, f, indent=2)

    with open(f"{out_dir}/per_class_metrics.json", "w") as f:
        json.dump(per_class, f, indent=2)

    with open(f"{out_dir}/roc_curves.json", "w") as f:
        json.dump(roc_data, f, indent=2)

    # Also update model_config accuracy fields
    config_path = "models/model_config.json"
    with open(config_path, "w") as f:
        json.dump({
            "architecture": "1D-CNN",
            "version": "v1.0.0",
            "input_shape": [1, 200],
            "num_classes": 5,
            "class_names": CLASS_NAMES,
            "overall_accuracy": round(accuracy, 4),
            "weighted_f1_score": round(weighted_f1, 4),
        }, f, indent=2)

    logger.info(f"✅ Evaluation complete. Artifacts saved to {out_dir}/")
    logger.info(f"   Accuracy: {accuracy:.4f} | Weighted F1: {weighted_f1:.4f}")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate trained 1D-CNN model")
    parser.add_argument("--mitbih", type=str, required=True, help="Path to MIT-BIH CSV folder")
    parser.add_argument("--model", type=str, default="models/best_model.pth", help="Path to model weights")
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()

    evaluate(args.mitbih, args.model, args.batch_size)
