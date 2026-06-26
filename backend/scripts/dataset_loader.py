import os
import glob
import wfdb
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from sklearn.model_selection import train_test_split
from scipy.signal import find_peaks, resample
import logging

logger = logging.getLogger(__name__)

# AAMI standard mappings for MIT-BIH
AAMI_MAPPING = {
    'N': 0, 'L': 0, 'R': 0, 'e': 0, 'j': 0,  # Normal
    'A': 1, 'a': 1, 'J': 1, 'S': 1,          # Supraventricular
    'V': 2, 'E': 2,                          # Ventricular
    'F': 3,                                  # Fusion
    '/': 4, 'f': 4, 'Q': 4                   # Unknown/Paced
}

class ECGDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.float32).unsqueeze(1)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

def normalize_beat(beat):
    std = np.std(beat)
    if std == 0:
        std = 1e-8
    return (beat - np.mean(beat)) / std

def load_mitbih(mitbih_dir: str):
    logger.info("Loading Raw MIT-BIH Dataset...")
    dat_files = glob.glob(os.path.join(mitbih_dir, "*.dat"))
    if not dat_files:
        logger.warning(f"No .dat files found in {mitbih_dir}")
        return [], []
        
    X_list, y_list = [], []
    for dat in dat_files:
        base_path = dat[:-4]
        try:
            record = wfdb.rdrecord(base_path)
            ann = wfdb.rdann(base_path, 'atr')
        except Exception as e:
            logger.warning(f"Failed to read {base_path}: {e}")
            continue
            
        lead_idx = 0
        if 'MLII' in record.sig_name:
            lead_idx = record.sig_name.index('MLII')
        elif 'II' in record.sig_name:
            lead_idx = record.sig_name.index('II')
            
        sig = record.p_signal[:, lead_idx]
        
        for i, sym in enumerate(ann.symbol):
            if sym in AAMI_MAPPING:
                peak = ann.sample[i]
                start = peak - 80
                end = peak + 120
                if start >= 0 and end < len(sig):
                    window = sig[start:end]
                    window = normalize_beat(window)
                    X_list.append(window)
                    y_list.append(AAMI_MAPPING[sym])
    
    return X_list, y_list

def load_ptb(ptb_dir: str):
    logger.info("Loading Raw PTB Diagnostic Dataset...")
    headers = glob.glob(os.path.join(ptb_dir, "**", "*.hea"), recursive=True)
    if not headers:
        logger.warning(f"No .hea files found in {ptb_dir}")
        return [], []
        
    X_list, y_list = [], []
    for hea_path in headers:
        base_path = hea_path[:-4]
        try:
            record = wfdb.rdrecord(base_path)
            header = wfdb.rdheader(base_path)
        except Exception as e:
            continue
            
        diagnosis = "abnormal"
        if header.comments:
            for comment in header.comments:
                if "Healthy control" in comment:
                    diagnosis = "normal"
                    break
        
        label = 0 if diagnosis == "normal" else 4
        
        lead_idx = 0
        for i, name in enumerate(record.sig_name):
            if name.upper() == 'II':
                lead_idx = i
                break
                
        sig = record.p_signal[:, lead_idx]
        # Remove NaNs
        sig = np.nan_to_num(sig)
        
        # PTB sampling is typically 1000Hz.
        # Find R-peaks (distance ~600ms, prominence high enough for R-peak)
        prominence = 0.5 * (np.max(sig) - np.median(sig))
        if prominence <= 0:
            prominence = 0.1
        peaks, _ = find_peaks(sig, distance=600, prominence=prominence)
        
        # 80/360s * 1000 = 222 samples. 120/360s * 1000 = 333 samples.
        for peak in peaks:
            start = peak - 222
            end = peak + 333
            if start >= 0 and end < len(sig):
                window = sig[start:end]
                # Downsample to 200 to match MIT-BIH
                window_200 = resample(window, 200)
                window_200 = normalize_beat(window_200)
                X_list.append(window_200)
                y_list.append(label)
                
    return X_list, y_list

def get_dataloaders(mitbih_dir: str, ptb_dir: str, batch_size=64):
    import pandas as pd
    
    csv_paths = [
        (os.path.join(mitbih_dir, "mitbih_train.csv"), os.path.join(mitbih_dir, "mitbih_test.csv")),
        ("datasets/mit-bih/mitbih_train.csv", "datasets/mit-bih/mitbih_test.csv"),
        (os.path.join(os.path.dirname(__file__), "..", "datasets", "mit-bih", "mitbih_train.csv"),
         os.path.join(os.path.dirname(__file__), "..", "datasets", "mit-bih", "mitbih_test.csv"))
    ]
    
    train_csv, test_csv = None, None
    for tr, te in csv_paths:
        if os.path.exists(tr) and os.path.exists(te):
            train_csv, test_csv = tr, te
            break
            
    if train_csv and test_csv:
        logger.info(f"Loading preprocessed MIT-BIH CSV datasets: {train_csv}, {test_csv}")
        train_df = pd.read_csv(train_csv, header=None)
        test_df = pd.read_csv(test_csv, header=None)
        
        X_train = train_df.iloc[:, :200].values.astype(np.float32)
        y_train = train_df.iloc[:, 200].values.astype(int)
        
        X_test = test_df.iloc[:, :200].values.astype(np.float32)
        y_test = test_df.iloc[:, 200].values.astype(int)
        
        if ptb_dir and os.path.exists(ptb_dir):
            X_ptb, y_ptb = load_ptb(ptb_dir)
            if len(X_ptb) > 0:
                X_ptb = np.array(X_ptb)
                y_ptb = np.array(y_ptb)
                X_ptb_train, X_ptb_test, y_ptb_train, y_ptb_test = train_test_split(
                    X_ptb, y_ptb, test_size=0.2, random_state=42, stratify=y_ptb
                )
                X_train = np.concatenate([X_train, X_ptb_train], axis=0)
                y_train = np.concatenate([y_train, y_ptb_train], axis=0)
                X_test = np.concatenate([X_test, X_ptb_test], axis=0)
                y_test = np.concatenate([y_test, y_ptb_test], axis=0)
    else:
        # Fallback to raw WFDB loading
        X_all, y_all = [], []
        X_mit, y_mit = load_mitbih(mitbih_dir)
        X_all.extend(X_mit)
        y_all.extend(y_mit)
        
        if ptb_dir and os.path.exists(ptb_dir):
            X_ptb, y_ptb = load_ptb(ptb_dir)
            X_all.extend(X_ptb)
            y_all.extend(y_ptb)
            
        if not X_all:
            raise ValueError("Could not extract any valid beats from the provided directories.")
            
        X_all = np.array(X_all)
        y_all = np.array(y_all, dtype=int)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X_all, y_all, test_size=0.2, random_state=42, stratify=y_all
        )
        
    logger.info(f"Train samples: {len(X_train)} | Test samples: {len(X_test)}")
    logger.info(f"Train class distribution: {np.bincount(y_train, minlength=5)}")
    
    train_dataset = ECGDataset(X_train, y_train)
    test_dataset = ECGDataset(X_test, y_test)

    # Calculate Class Weights for WeightedRandomSampler or CrossEntropyLoss
    class_counts = np.bincount(y_train, minlength=5)
    total = len(y_train)
    # Handle classes with 0 samples safely
    class_weights = [total / c if c > 0 else 0.0 for c in class_counts]
    class_weights = torch.FloatTensor(class_weights)
    
    # Optionally, oversampling using WeightedRandomSampler
    sample_weights = [class_weights[label] for label in y_train]
    sampler = WeightedRandomSampler(weights=sample_weights, num_samples=len(sample_weights), replacement=True)

    # Use sampler in training loader for class balancing
    train_loader = DataLoader(train_dataset, batch_size=batch_size, sampler=sampler)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    return train_loader, test_loader, class_weights
