"""
model_config.py
Defines the ECGClassifier 1D-CNN architecture exactly as specified in the
CardioFPGA research paper (Section 3, Table 1).

Architecture (per research paper):
  Input: [batch, 1, 200]   (200-sample heartbeat window, Z-score normalized)
  Conv1D(1→8, K=5, S=1) → BN → ReLU → MaxPool(P=2)   → [B, 8, 98]
  Conv1D(8→16, K=5, S=1) → BN → ReLU → MaxPool(P=2)  → [B, 16, 47]
  Flatten                                               → [B, 752]  (16×47)
  FC(752→64) → ReLU → Dropout
  FC(64→32) → ReLU → Dropout
  FC(32→5)  → Output logits (N, S, V, F, Q)

Reference: CardioFPGA Research Paper, Section 3.2, Table of Layer Configurations
Hardware: Xilinx Zynq-7020 (XC7Z020-CLG484-1), 100 MHz clock
"""

import os
import json
import torch
import torch.nn as nn


class ConvBlock(nn.Module):
    """Conv1D → BatchNorm → ReLU → MaxPool → Dropout"""
    def __init__(self, in_ch: int, out_ch: int, kernel_size: int, dropout: float = 0.2):
        super().__init__()
        # Same-ish padding for the conv (paper uses no padding, output shrinks by K-1)
        self.conv = nn.Conv1d(in_ch, out_ch, kernel_size, padding=0)
        self.bn = nn.BatchNorm1d(out_ch)
        self.relu = nn.ReLU()
        self.pool = nn.MaxPool1d(2)
        self.drop = nn.Dropout(dropout)

    def forward(self, x):
        return self.drop(self.pool(self.relu(self.bn(self.conv(x)))))


class ECGClassifier(nn.Module):
    """
    1D-CNN ECG Arrhythmia Classifier per CardioFPGA Research Paper.

    Exactly matches Table 1 in Section 3.2:
      Layer 0:  Input          [B, 1, 200]
      Layer 1:  Conv1D(K=5)    [B, 8, 196]  → BN → ReLU
      Layer 2:  MaxPool(P=2)   [B, 8, 98]
      Layer 3:  Conv1D(K=5)    [B, 16, 94]  → BN → ReLU
      Layer 4:  MaxPool(P=2)   [B, 16, 47]
      Layer 5:  Flatten        [B, 752]
      Layer 6:  FC1(752→64)    → ReLU
      Layer 7:  FC2(64→32)     → ReLU
      Layer 8:  Out(32→5)      → logits

    Total trainable parameters: ~52,661
    """

    NUM_CLASSES = 5
    INPUT_LEN = 200

    # AAMI EC57 standard class labels
    CLASS_NAMES = ["Normal", "Supraventricular", "Ventricular", "Fusion", "Unknown"]

    def __init__(self):
        super().__init__()
        # Stage 1: Conv1D(1→8, K=5) → BN → ReLU → MaxPool → Dropout
        # Input: [B, 1, 200] → after conv(K=5): [B, 8, 196] → after pool: [B, 8, 98]
        self.conv1 = ConvBlock(1, 8, kernel_size=5, dropout=0.2)

        # Stage 2: Conv1D(8→16, K=5) → BN → ReLU → MaxPool → Dropout
        # Input: [B, 8, 98] → after conv(K=5): [B, 16, 94] → after pool: [B, 16, 47]
        self.conv2 = ConvBlock(8, 16, kernel_size=5, dropout=0.2)

        # Flatten: [B, 16, 47] → [B, 752]
        self.flatten = nn.Flatten()

        # FC1: 752 → 64, ReLU, Dropout
        self.fc1 = nn.Sequential(
            nn.Linear(16 * 47, 64),
            nn.ReLU(),
            nn.Dropout(0.5),
        )

        # FC2: 64 → 32, ReLU, Dropout
        self.fc2 = nn.Sequential(
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.5),
        )

        # Output: 32 → 5 class logits
        self.out = nn.Linear(32, self.NUM_CLASSES)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.
        Args:
            x: [B, 1, 200] — batch of normalized heartbeat segments
        Returns:
            logits: [B, 5] — raw class logits (apply softmax for probabilities)
        """
        x = self.conv1(x)   # [B, 8, 98]
        x = self.conv2(x)   # [B, 16, 47]
        x = self.flatten(x) # [B, 752]
        x = self.fc1(x)     # [B, 64]
        x = self.fc2(x)     # [B, 32]
        return self.out(x)  # [B, 5]


# Architecture reference constants (from research paper Section 3.2)
MODEL_CONFIG = {
    "architecture": "1D-CNN",
    "version": "v1.0.0",
    "description": "CardioFPGA 1D-CNN per research paper Section 3",
    "input_shape": [1, 200],  # [channels, time_samples]
    "num_classes": 5,
    "class_names": ECGClassifier.CLASS_NAMES,
    "layer_config": [
        {"name": "conv1", "type": "Conv1D", "in_ch": 1, "out_ch": 8, "kernel": 5},
        {"name": "conv2", "type": "Conv1D", "in_ch": 8, "out_ch": 16, "kernel": 5},
        {"name": "fc1", "type": "Linear", "in": 752, "out": 64},
        {"name": "fc2", "type": "Linear", "in": 64, "out": 32},
        {"name": "out", "type": "Linear", "in": 32, "out": 5},
    ],
    # Hardware target (per research paper Section 6.3)
    "fpga_target": {
        "device": "xc7z020clg484-1",
        "family": "Zynq-7000",
        "clock_mhz": 100,
        "pipeline_cycles": 152,
        "latency_us": 1.52,
        "throughput_beats_per_sec": 6578,
    },
    # Published INT8 quantization results (research paper Section 6.2)
    "published_metrics": {
        "fp32_accuracy": 0.978,   # 97.8%
        "int8_accuracy": 0.976,   # 97.6%
        "accuracy_drop": 0.002,   # 0.2%
        "fp32_size_mb": 3.40,
        "int8_size_mb": 0.85,
        "compression_ratio": 4.0,
        "source": "research_paper_section_6",
        "note": "Published baseline; use get_real_metrics() for actual trained model values",
    },
}

# Legacy alias
CLASS_NAMES = ECGClassifier.CLASS_NAMES


def get_real_metrics() -> dict:
    """
    Load actual training metrics from generated/metrics.json if it exists.
    The file is produced by running scripts/train_model.py.

    Returns:
        dict with keys: accuracy, f1_macro, precision_weighted, recall_weighted, source
        Returns empty dict {} if no training has been done yet.
    """
    search_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "generated", "metrics.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "generated", "metrics.json"),
        os.path.join(os.path.dirname(__file__), "..", "generated", "metrics.json"),
        "generated/metrics.json",
    ]
    for path in search_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r") as f:
                    raw = json.load(f)
                # Handle sklearn classification_report format
                # Keys: class labels + "accuracy", "macro avg", "weighted avg"
                accuracy = raw.get("accuracy")
                macro = raw.get("macro avg") or {}
                weighted = raw.get("weighted avg") or {}
                return {
                    "accuracy": round(float(accuracy), 4) if accuracy is not None else None,
                    "f1_macro": round(float(macro.get("f1-score", 0)), 4) if macro else None,
                    "precision_weighted": round(float(weighted.get("precision", 0)), 4) if weighted else None,
                    "recall_weighted": round(float(weighted.get("recall", 0)), 4) if weighted else None,
                    "source": "trained_model",
                    "metrics_path": abs_path,
                }
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(f"Failed to read metrics.json at {abs_path}: {exc}")
                continue
    return {}


def get_training_history() -> list:
    """
    Load training loss/accuracy per-epoch history from generated/history.json.
    The file is produced by running scripts/train_model.py.

    Returns:
        list of dicts with keys: epoch, train_acc, val_acc, train_loss, val_loss
        Returns empty list [] if no training has been done yet.
    """
    search_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "generated", "history.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "generated", "history.json"),
        os.path.join(os.path.dirname(__file__), "..", "generated", "history.json"),
        "generated/history.json",
    ]
    for path in search_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r") as f:
                    return json.load(f)
            except Exception as exc:
                import logging
                logging.getLogger(__name__).warning(f"Failed to read history.json at {abs_path}: {exc}")
                continue
    return []


def get_published_metrics() -> dict:
    """
    Returns the published baseline metrics from the research paper.
    Used as reference only — prefer get_real_metrics() for actual trained values.
    """
    return MODEL_CONFIG["published_metrics"].copy()
