# CardioFPGA Backend — Developer Startup Guide

## Quick Start (Local Development)

### Prerequisites
- Python 3.10+
- Docker Desktop (for MongoDB, Redis, MinIO)
- Node 18+ (for the frontend)

---

## 1. Start Infrastructure Services

```powershell
# In backend/ directory — starts MongoDB, Redis, MinIO only
docker-compose up mongodb redis minio -d
```

Check MinIO console at http://localhost:9001 (user: `minioadmin`, pass: `minioadmin`)

---

## 2. Install Python Dependencies

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 3. Train the ML Model (one-time)

```powershell
# Download MIT-BIH dataset from Kaggle:
# https://www.kaggle.com/datasets/shayanfazeli/heartbeat
# Place mitbih_train.csv and mitbih_test.csv in datasets/mit-bih/

python scripts/train_model.py --mitbih datasets/mit-bih --epochs 20 --batch-size 128
```

After training completes, evaluate the model:
```powershell
python scripts/evaluate_model.py --mitbih datasets/mit-bih
```

---

## 4. Start the FastAPI Backend

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs  
Health:   http://localhost:8000/health

---

## 5. Start the Celery Worker (separate terminal)

```powershell
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2
```

---

## 6. Start the Frontend

```powershell
cd ../pulse-analytics
npm install
npm run dev
```

Frontend: http://localhost:5173

---

## 7. Generate Test Data (optional — no MATLAB needed)

```powershell
cd backend
python scripts/generate_sample_data.py --output test_data --duration 30
```

---

## End-to-End Test Flow

```powershell
# 1. Create session
$SESSION = (Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/session/init" `
  -ContentType "application/json" -Body "{}").session_id

Write-Host "Session: $SESSION"

# 2. Upload test files
$headers = @{ "X-Session-ID" = $SESSION }
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/upload/matlab" `
  -Headers $headers `
  -Form @{
    ecg_signal        = Get-Item "test_data/ecg_signal.csv"
    filtered_signal   = Get-Item "test_data/filtered_signal.csv"
    rpeaks            = Get-Item "test_data/rpeaks.csv"
    beat_segments     = Get-Item "test_data/beat_segments.csv"
  }

# 3. Start inference (connect WS for progress)
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/api/v1/inference/start" `
  -Headers $headers -ContentType "application/json" -Body "{}"

# 4. Poll status
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/inference/status" -Headers $headers

# 5. Get dashboard
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/analytics/dashboard" -Headers $headers
```

---

## Full Docker Stack (Production)

```powershell
# Build and start everything
docker-compose up --build -d

# Monitor logs
docker-compose logs -f api celery_worker

# Celery Flower dashboard
# http://localhost:5555
```

---

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/session/init` | Create a new analysis session |
| POST | `/api/v1/upload/matlab` | Upload 4 MATLAB CSV files |
| POST | `/api/v1/inference/start` | Start AI inference |
| GET | `/api/v1/inference/status` | Poll inference progress |
| GET | `/api/v1/inference/results` | Get full predictions |
| POST | `/api/v1/quantization/start` | INT8 quantize model |
| POST | `/api/v1/hex/generate` | Generate FPGA HEX files |
| GET | `/api/v1/hex/download` | Download fpga_weights.zip |
| POST | `/api/v1/fpga/upload` | Upload Vivado reports |
| GET | `/api/v1/fpga/results` | Get parsed FPGA metrics |
| GET | `/api/v1/analytics/dashboard` | Full dashboard data |
| WS | `/ws/session/{session_id}` | Real-time progress stream |

All endpoints (except `/session/init`) require `X-Session-ID` header.
