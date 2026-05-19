import torch
import os
import argparse
from app.ml.model_config import ECGClassifier

def create_mock_weights():
    """Create a dummy weights file for testing if no real model exists."""
    os.makedirs("models", exist_ok=True)
    model = ECGClassifier()
    # Ensure it outputs something plausible
    path = "models/best_model.pth"
    torch.save(model.state_dict(), path)
    print(f"Created mock model weights at {path}")

if __name__ == "__main__":
    create_mock_weights()
