import os
import glob
import numpy as np
import pandas as pd
import wfdb
from sklearn.model_selection import train_test_split
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AAMI standard mappings
CLASS_MAPPING = {
    'N': 0, 'L': 0, 'R': 0, 'e': 0, 'j': 0,  # Normal
    'A': 1, 'a': 1, 'J': 1, 'S': 1,          # Supraventricular
    'V': 2, 'E': 2,                          # Ventricular
    'F': 3,                                  # Fusion
    '/': 4, 'f': 4, 'Q': 4                   # Unknown/Paced
}

def extract_beats(record_path, window_size=200):
    """Extract beats from a single WFDB record."""
    try:
        # Read signal and annotations
        record = wfdb.rdrecord(record_path)
        annotation = wfdb.rdann(record_path, 'atr')
        
        # Usually lead 0 (MLII) is used for beat classification
        signal = record.p_signal[:, 0]
        
        beats = []
        labels = []
        
        # For each annotation, extract a window around the R-peak
        half_window = window_size // 2
        for i, (sample, symbol) in enumerate(zip(annotation.sample, annotation.symbol)):
            if symbol in CLASS_MAPPING:
                # Ensure window is within signal bounds
                if sample - half_window >= 0 and sample + half_window < len(signal):
                    beat = signal[sample - half_window:sample + half_window]
                    beats.append(beat)
                    labels.append(CLASS_MAPPING[symbol])
                    
        return np.array(beats), np.array(labels)
    except Exception as e:
        logger.error(f"Error processing {record_path}: {e}")
        return np.array([]), np.array([])

def process_mitbih(source_dir, output_dir):
    """Process all MIT-BIH records and save as train/test CSVs."""
    logger.info(f"Processing MIT-BIH records from {source_dir}")
    
    # Get all record names (remove extension)
    record_files = glob.glob(os.path.join(source_dir, "*.dat"))
    records = [os.path.splitext(f)[0] for f in record_files]
    
    all_beats = []
    all_labels = []
    
    for record_path in records:
        logger.info(f"Extracting {os.path.basename(record_path)}")
        beats, labels = extract_beats(record_path)
        if len(beats) > 0:
            all_beats.append(beats)
            all_labels.append(labels)
            
    if not all_beats:
        logger.error("No beats extracted from MIT-BIH database.")
        return
        
    X = np.vstack(all_beats)
    y = np.concatenate(all_labels)
    
    # Stratified split for train and test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Combine features and labels
    train_data = np.hstack((X_train, y_train.reshape(-1, 1)))
    test_data = np.hstack((X_test, y_test.reshape(-1, 1)))
    
    logger.info(f"Saving training data: {train_data.shape}")
    pd.DataFrame(train_data).to_csv(os.path.join(output_dir, "mitbih_train.csv"), header=False, index=False)
    
    logger.info(f"Saving testing data: {test_data.shape}")
    pd.DataFrame(test_data).to_csv(os.path.join(output_dir, "mitbih_test.csv"), header=False, index=False)
    
    logger.info("MIT-BIH preprocessing complete.")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mitbih_source = os.path.join(base_dir, "app", "database", "mit-bih-arrhythmia-database-1.0.0")
    mitbih_output = os.path.join(base_dir, "datasets", "mit-bih")
    
    os.makedirs(mitbih_output, exist_ok=True)
    process_mitbih(mitbih_source, mitbih_output)
