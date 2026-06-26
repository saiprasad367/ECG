"""
backfill_sessions.py
Reconstruct session.json persistence files for all sessions that have uploaded CSV files
but no session.json (i.e., sessions uploaded before session persistence was added).

Run from backend/ directory:
    python scripts/backfill_sessions.py
"""
import sys, os, json, uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from app.utils.validators import estimate_duration
from app.config import settings

STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "sessions"))

FILE_KEYS = ["ecg_signal", "filtered_signal", "rpeaks", "beat_segments"]
BUCKET = settings.MINIO_BUCKET


def find_latest_file(uploads_dir: str, key: str) -> str | None:
    """Find the most recently modified CSV that starts with the given key."""
    try:
        matches = [
            f for f in os.listdir(uploads_dir)
            if f.lower().endswith(".csv") and os.path.splitext(f)[0].startswith(key)
        ]
        if not matches:
            return None
        matches.sort(key=lambda x: os.path.getmtime(os.path.join(uploads_dir, x)), reverse=True)
        return matches[0]
    except Exception:
        return None


def parse_metadata(key_files: dict, uploads_dir: str, session_id: str) -> tuple[dict, dict]:
    """Parse metadata and build stored-files dict from CSV files on disk."""
    stored = {}
    for key, filename in key_files.items():
        filepath = os.path.join(uploads_dir, filename)
        size = os.path.getsize(filepath)
        obj_name = f"sessions/{session_id}/uploads/{filename}"
        stored[key] = {
            "filename": filename,
            "size_bytes": size,
            "storage_path": f"s3://{BUCKET}/{obj_name}",
            "object_name": obj_name,
        }

    # --- Beat count from rpeaks ---
    total_beats = 0
    rpeak_file = key_files.get("rpeaks")
    if rpeak_file:
        try:
            df_r = pd.read_csv(os.path.join(uploads_dir, rpeak_file))
            total_beats = len(df_r)
        except Exception as e:
            print(f"  Warning: could not read rpeaks: {e}")

    if total_beats == 0:
        beat_file = key_files.get("beat_segments")
        if beat_file:
            try:
                df_b = pd.read_csv(os.path.join(uploads_dir, beat_file))
                numeric_cols = df_b.select_dtypes(include=["number"]).columns
                if len(numeric_cols) >= 10:
                    total_beats = len(df_b)
                else:
                    id_col = next((c for c in df_b.columns if c.lower() in ["beat_id", "beat_index", "index"]), None)
                    total_beats = df_b[id_col].nunique() if id_col else len(df_b)
            except Exception as e:
                print(f"  Warning: could not read beat_segments: {e}")

    # --- Duration from ecg_signal ---
    duration = 0.0
    num_samples = 0
    ecg_file = key_files.get("ecg_signal")
    if ecg_file:
        try:
            df_ecg = pd.read_csv(os.path.join(uploads_dir, ecg_file))
            num_samples = len(df_ecg)
            duration = estimate_duration(df_ecg, 360)
        except Exception as e:
            print(f"  Warning: could not read ecg_signal: {e}")

    metadata = {
        "total_beats": int(total_beats),
        "duration_seconds": round(float(duration), 2),
        "sampling_rate": 360,
        "signal_quality": "good",
        "num_samples": int(num_samples),
    }

    return stored, metadata


def build_session_doc(session_id: str, stored: dict, metadata: dict) -> dict:
    from datetime import datetime, timedelta
    now = datetime.utcnow().isoformat()
    expires = (datetime.utcnow() + timedelta(hours=168)).isoformat()

    return {
        "_id": session_id,
        "created_at": now,
        "last_activity": now,
        "expires_at": expires,
        "status": "active",
        "client_info": {"ip_address": "backfilled", "user_agent": "backfill_sessions.py"},
        "matlab_upload": {
            "upload_id": str(uuid.uuid4()),
            "files": stored,
            "metadata": metadata,
            "uploaded_at": now,
        },
        "vivado_upload": None,
        "inference": None,
        "quantization": None,
        "hex_generation": None,
        "fpga_analysis": None,
        "progress": {
            "matlab_upload": True,
            "inference": False,
            "quantization": False,
            "hex_generation": False,
            "fpga_upload": False,
            "fpga_analysis": False,
        },
    }


def main():
    if not os.path.isdir(STORAGE_DIR):
        print(f"No sessions directory found at {STORAGE_DIR}")
        return

    sessions = [d for d in os.listdir(STORAGE_DIR) if os.path.isdir(os.path.join(STORAGE_DIR, d))]
    print(f"Found {len(sessions)} session directories.\n")

    for session_id in sessions:
        sess_dir = os.path.join(STORAGE_DIR, session_id)
        uploads_dir = os.path.join(sess_dir, "uploads")
        session_json = os.path.join(sess_dir, "session.json")

        if os.path.exists(session_json):
            print(f"[SKIP] {session_id} — session.json already exists")
            continue

        if not os.path.isdir(uploads_dir):
            print(f"[SKIP] {session_id} — no uploads/ directory")
            continue

        # Find the latest version of each CSV key
        key_files = {}
        for key in FILE_KEYS:
            f = find_latest_file(uploads_dir, key)
            if f:
                key_files[key] = f

        if len(key_files) < 4:
            print(f"[SKIP] {session_id} — only {len(key_files)}/4 file types found: {list(key_files.keys())}")
            continue

        print(f"[FIX ] {session_id}")
        print(f"  Files: {key_files}")

        stored, metadata = parse_metadata(key_files, uploads_dir, session_id)

        print(f"  Total beats: {metadata['total_beats']}")
        print(f"  Duration: {metadata['duration_seconds']}s")
        print(f"  Num samples: {metadata['num_samples']}")

        doc = build_session_doc(session_id, stored, metadata)

        # Save session.json
        tmp = session_json + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, default=str)
        os.replace(tmp, session_json)
        print(f"  OK Written: {session_json}\n")

    print("Backfill complete!")


if __name__ == "__main__":
    main()
