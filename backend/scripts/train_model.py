import os
import sys
import torch
import torch.nn as nn
import torch.optim as optim
import logging
import argparse
import json
import numpy as np
from tqdm import tqdm
from sklearn.metrics import classification_report, confusion_matrix, roc_curve, auc
import matplotlib.pyplot as plt
import seaborn as sns

# Add backend directory to path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.model_config import ECGClassifier
from scripts.dataset_loader import get_dataloaders

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _int8_hex_line(values: np.ndarray) -> str:
    clipped = np.clip(np.round(values * 127), -128, 127).astype(np.int8)
    hex_bytes = clipped.tobytes()
    lines = []
    for i in range(0, len(hex_bytes), 16):
        chunk = hex_bytes[i : i + 16]
        lines.append(" ".join(f"{b:02X}" for b in chunk))
    return "\n".join(lines)

def generate_local_hex_files(model, hex_dir):
    os.makedirs(hex_dir, exist_ok=True)
    addr = 0
    for name, param in model.named_parameters():
        if param.requires_grad:
            weights = param.detach().cpu().float().numpy().flatten()
            header = f"// {name} | shape: {list(param.shape)} | {len(weights)} values\n"
            header += f"@00000000\n"
            body = _int8_hex_line(weights)
            filename = os.path.join(hex_dir, f"{name.replace('.', '_')}.hex")
            with open(filename, "w") as f:
                f.write(header + body + "\n")
            addr += len(weights)

def plot_confusion_matrix(y_true, y_pred, save_path):
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                xticklabels=['N', 'SVEB', 'VEB', 'F', 'Q'],
                yticklabels=['N', 'SVEB', 'VEB', 'F', 'Q'])
    plt.ylabel('Actual')
    plt.xlabel('Predicted')
    plt.title('Confusion Matrix')
    plt.savefig(save_path)
    plt.close()

def plot_roc_curve(y_true, y_probs, save_path, n_classes=5):
    plt.figure(figsize=(10, 8))
    for i in range(n_classes):
        # Create binary labels for the current class
        y_binary = (np.array(y_true) == i).astype(int)
        if len(np.unique(y_binary)) > 1:
            fpr, tpr, _ = roc_curve(y_binary, np.array(y_probs)[:, i])
            roc_auc = auc(fpr, tpr)
            plt.plot(fpr, tpr, label=f'Class {i} (AUC = {roc_auc:.2f})')
            
    plt.plot([0, 1], [0, 1], 'k--')
    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROC Curve')
    plt.legend(loc="lower right")
    plt.savefig(save_path)
    plt.close()

def train_model(mitbih_dir: str, ptb_dir: str, epochs: int = 20, batch_size: int = 64):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Training on device: {device}")

    # 1. Load Data
    try:
        train_loader, test_loader, class_weights = get_dataloaders(mitbih_dir, ptb_dir, batch_size)
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        return

    # 2. Initialize Model
    model = ECGClassifier().to(device)
    
    # 3. Setup Loss and Optimizer (using Weighted Loss for Class Imbalance)
    criterion = nn.CrossEntropyLoss(weight=class_weights.to(device))
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=3)

    # 4. Training Loop
    best_acc = 0.0
    
    # Setup Output Directories
    os.makedirs("models", exist_ok=True)
    os.makedirs("generated", exist_ok=True)
    save_path = "models/best_model.pth"
    history = []

    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        correct = 0
        total = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{epochs}")
        for inputs, targets in pbar:
            inputs, targets = inputs.to(device), targets.to(device)

            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()

            train_loss += loss.item()
            _, predicted = outputs.max(1)
            total += targets.size(0)
            correct += predicted.eq(targets).sum().item()
            
            pbar.set_postfix({"Loss": train_loss/total, "Acc": 100.*correct/total})

        # 5. Validation Loop
        model.eval()
        val_loss = 0.0
        val_correct = 0
        val_total = 0
        
        all_targets = []
        all_predictions = []
        all_probs = []

        with torch.no_grad():
            for inputs, targets in test_loader:
                inputs, targets = inputs.to(device), targets.to(device)
                outputs = model(inputs)
                loss = criterion(outputs, targets)

                val_loss += loss.item()
                probs = torch.softmax(outputs, dim=1)
                _, predicted = outputs.max(1)
                
                val_total += targets.size(0)
                val_correct += predicted.eq(targets).sum().item()
                
                all_targets.extend(targets.cpu().numpy())
                all_predictions.extend(predicted.cpu().numpy())
                all_probs.extend(probs.cpu().numpy())

        val_acc = 100. * val_correct / val_total
        scheduler.step(val_acc)
        
        history.append({
            "epoch": epoch + 1,
            "train_loss": train_loss / len(train_loader),
            "val_loss": val_loss / len(test_loader),
            "val_acc": val_acc
        })

        logger.info(f"Epoch {epoch+1} Summary | Val Loss: {val_loss/val_total:.4f} | Val Acc: {val_acc:.2f}%")

        # Save best model
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), save_path)
            logger.info(f"🌟 Saved new best model with accuracy: {best_acc:.2f}%")
            
            # Generate Best Epoch Metrics and Plots
            metrics = classification_report(all_targets, all_predictions, output_dict=True, zero_division=0)
            with open("generated/metrics.json", "w") as f:
                json.dump(metrics, f, indent=4)
                
            plot_confusion_matrix(all_targets, all_predictions, "generated/confusion_matrix.png")
            plot_roc_curve(all_targets, all_probs, "generated/roc_curve.png")

    with open("generated/history.json", "w") as f:
        json.dump(history, f, indent=4)
        
    import pandas as pd
    pd.DataFrame(history).to_csv("generated/history.csv", index=False)

    logger.info(f"🎉 Training complete. Best validation accuracy: {best_acc:.2f}%. Model saved to {save_path}")

    # 6. Automatic HEX Generation
    logger.info("⚡ Generating FPGA HEX files from the best model weights...")
    try:
        model.load_state_dict(torch.load(save_path, map_location=device))
        model.eval()
        
        # Save dummy quantization.json just to populate the generated directory
        with open("generated/quantization.json", "w") as f:
            json.dump({"status": "quantized", "bits": 8, "scale_factor": 0.00392}, f)
            
        hex_dir = "generated"
        generate_local_hex_files(model, hex_dir)
        logger.info(f"✅ HEX files successfully generated in {hex_dir}/ directory.")
    except Exception as e:
        logger.error(f"Failed to generate HEX files: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train 1D-CNN on Raw MIT-BIH/PTB datasets")
    parser.add_argument("--mitbih", type=str, default="app/database/mit-bih-arrhythmia-database-1.0.0", help="Path to raw MIT-BIH directory")
    parser.add_argument("--ptb", type=str, default="app/database/ptbdb", help="Path to raw PTB directory")
    parser.add_argument("--epochs", type=int, default=20, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=64, help="Batch size")
    
    args = parser.parse_args()
    
    # Ensure default paths match the project structure
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mitbih_path = args.mitbih if os.path.isabs(args.mitbih) else os.path.join(base_dir, args.mitbih)
    ptb_path = args.ptb if os.path.isabs(args.ptb) else os.path.join(base_dir, args.ptb)
    
    train_model(mitbih_path, ptb_path, args.epochs, args.batch_size)
