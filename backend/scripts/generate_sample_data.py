"""
generate_sample_data.py
Generates synthetic MATLAB-style CSV files for testing the upload/inference
pipeline without real MATLAB hardware.

Outputs (in the specified directory):
  ecg_signal.csv       — Raw ECG waveform (time, amplitude)
  filtered_signal.csv  — Bandpass-filtered waveform (time, amplitude)
  rpeaks.csv           — R-peak sample indices
  beat_segments.csv    — Segmented beats (wide format: each row = 1 beat, 200 samples)

Usage (from backend/ directory):
  python scripts/generate_sample_data.py --output test_data/

Then upload with curl:
  SESSION=$(curl -s -X POST http://localhost:8000/api/v1/session/init -H "Content-Type: application/json" -d '{}' | python -c "import sys,json; print(json.load(sys.stdin)['session_id'])")
  curl -X POST http://localhost:8000/api/v1/upload/matlab \\
    -H "X-Session-ID: $SESSION" \\
    -F "ecg_signal=@test_data/ecg_signal.csv" \\
    -F "filtered_signal=@test_data/filtered_signal.csv" \\
    -F "rpeaks=@test_data/rpeaks.csv" \\
    -F "beat_segments=@test_data/beat_segments.csv"
"""

import os
import argparse
import numpy as np
import pandas as pd

# Reproducible
np.random.seed(42)

SAMPLING_RATE = 360     # Hz — MIT-BIH standard
DURATION_SEC  = 30      # seconds of signal
N_SAMPLES     = SAMPLING_RATE * DURATION_SEC
BEAT_LEN      = 200     # samples per beat segment


def simulate_ecg(n_samples: int, sr: int = 360) -> np.ndarray:
    """Simulate a realistic ECG waveform using a sum of Gaussians per beat."""
    t = np.linspace(0, n_samples / sr, n_samples)
    signal = np.zeros(n_samples)

    # Approximate 75 bpm → period ~0.8 s
    heart_rate_hz = 75 / 60
    beat_period = sr / heart_rate_hz

    beat_starts = np.arange(0, n_samples, beat_period, dtype=int)

    for bs in beat_starts:
        # P-wave
        for offset, amp, width in [
            (int(sr * 0.12), 0.15, int(sr * 0.04)),    # P
            (int(sr * 0.18), -0.05, int(sr * 0.01)),   # Q
            (int(sr * 0.20), 1.0, int(sr * 0.015)),    # R (peak)
            (int(sr * 0.22), -0.10, int(sr * 0.01)),   # S
            (int(sr * 0.35), 0.20, int(sr * 0.05)),    # T
        ]:
            center = bs + offset
            if 0 < center < n_samples:
                gauss = amp * np.exp(
                    -0.5 * ((np.arange(n_samples) - center) / width) ** 2
                )
                signal += gauss

    # Add realistic baseline wander and noise
    baseline = 0.05 * np.sin(2 * np.pi * 0.1 * t)
    noise = np.random.normal(0, 0.02, n_samples)
    return signal + baseline + noise


def bandpass_filter(signal: np.ndarray) -> np.ndarray:
    """Simple moving average as stand-in for bandpass filter."""
    from scipy.ndimage import uniform_filter1d
    try:
        return uniform_filter1d(signal, size=5)
    except ImportError:
        return np.convolve(signal, np.ones(5) / 5, mode="same")


def detect_rpeaks(signal: np.ndarray, sr: int = 360) -> np.ndarray:
    """Simple threshold-based R-peak detection."""
    min_dist = int(sr * 0.5)   # 0.5 s refractory period
    threshold = np.max(signal) * 0.6

    peaks = []
    i = 0
    while i < len(signal) - 1:
        if signal[i] > threshold:
            # find local max
            start = i
            while i < len(signal) - 1 and signal[i + 1] >= signal[i]:
                i += 1
            peaks.append(i)
            i += min_dist
        else:
            i += 1
    return np.array(peaks, dtype=int)


def segment_beats(signal: np.ndarray, rpeaks: np.ndarray, beat_len: int = BEAT_LEN) -> np.ndarray:
    """Cut signal around each R-peak into fixed-length segments."""
    pre = beat_len // 2
    post = beat_len - pre
    beats = []
    for rp in rpeaks:
        start = rp - pre
        end = rp + post
        if start < 0 or end > len(signal):
            continue
        segment = signal[start:end]
        if len(segment) == beat_len:
            beats.append(segment)
    return np.array(beats, dtype=np.float32)


def generate(output_dir: str, n_samples: int = N_SAMPLES, sr: int = SAMPLING_RATE):
    os.makedirs(output_dir, exist_ok=True)

    print(f"Generating {n_samples / sr:.1f}s of synthetic ECG at {sr} Hz...")
    t = np.linspace(0, n_samples / sr, n_samples)

    # Raw signal
    raw = simulate_ecg(n_samples, sr)

    # Filtered signal
    filtered = bandpass_filter(raw)

    # R-peaks
    rpeaks = detect_rpeaks(filtered, sr)
    print(f"  Detected {len(rpeaks)} R-peaks")

    # Beat segments
    beats = segment_beats(filtered, rpeaks)
    print(f"  Segmented {len(beats)} beats ({beats.shape})")

    # ── Save CSVs ──────────────────────────────────────────────────────────────

    # ecg_signal.csv — (time, amplitude)
    pd.DataFrame({"time": t, "amplitude": raw}).to_csv(
        os.path.join(output_dir, "ecg_signal.csv"), index=False
    )

    # filtered_signal.csv — (time, amplitude)
    pd.DataFrame({"time": t, "amplitude": filtered}).to_csv(
        os.path.join(output_dir, "filtered_signal.csv"), index=False
    )

    # rpeaks.csv — (peak_index, peak_time)
    pd.DataFrame({
        "peak_index": rpeaks,
        "peak_time": t[rpeaks],
    }).to_csv(os.path.join(output_dir, "rpeaks.csv"), index=False)

    # beat_segments.csv — wide format: each row = 1 beat, columns = sample_0..sample_199
    cols = [f"sample_{i}" for i in range(beats.shape[1])]
    pd.DataFrame(beats, columns=cols).to_csv(
        os.path.join(output_dir, "beat_segments.csv"), index=False
    )

    print(f"\n✅ Files written to '{output_dir}/':")
    for fname in ["ecg_signal.csv", "filtered_signal.csv", "rpeaks.csv", "beat_segments.csv"]:
        path = os.path.join(output_dir, fname)
        size_kb = os.path.getsize(path) / 1024
        print(f"   {fname:30s}  {size_kb:8.1f} KB")

    print("\nTo upload these files, start the backend and run:")
    print('  SESSION=$(curl -s -X POST http://localhost:8000/api/v1/session/init \\')
    print('    -H "Content-Type: application/json" -d \'{}\' \\')
    print('    | python -c "import sys,json; print(json.load(sys.stdin)[\'session_id\'])")')
    print(f'  curl -X POST http://localhost:8000/api/v1/upload/matlab \\')
    print(f'    -H "X-Session-ID: $SESSION" \\')
    for fname in ["ecg_signal", "filtered_signal", "rpeaks", "beat_segments"]:
        print(f'    -F "{fname}=@{output_dir}/{fname}.csv" \\')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic MATLAB ECG test data")
    parser.add_argument("--output", type=str, default="test_data", help="Output directory")
    parser.add_argument("--duration", type=int, default=30, help="Signal duration in seconds")
    parser.add_argument("--sr", type=int, default=360, help="Sampling rate (Hz)")
    args = parser.parse_args()
    generate(args.output, args.duration * args.sr, args.sr)
