# CardioFPGA: Clinical-Grade ECG Arrhythmia Classification & FPGA Synthesis Pipeline

CardioFPGA is an end-to-end medical edge intelligence framework that trains a 1D Convolutional Neural Network (1D-CNN) for clinical ECG arrhythmia detection, quantizes model weights to low-power INT8 representations, maps weights directly to memory block layouts, and validates synthesized FPGA designs using automated hardware-in-the-loop (HIL) diagnostics.

## 📄 Research Paper Document
A comprehensive, publication-grade academic research manuscript describing the mathematical formulations (resampling, normalization, quantization, slack timing constraints) and cross-platform benchmarks is included at:
👉 **[RESEARCH_PAPER.md](./RESEARCH_PAPER.md)**

---

## 🏗️ Project Architecture & Components

The workspace is organized into two primary applications:

### 1. Backend Service (`/backend`)
A FastAPI server integrating the machine learning models, database simulation, and Vivado synthesis parsing routines:
* **ML Inference & Optimization (`/backend/app/ml`):** Python pipelines for 1D-CNN training, Z-score amplitude normalization, polyphase resampling, and post-training INT8 quantization.
* **HEX File Compiler:** Translates quantized weights to Intel HEX standard formats for Block RAM (BRAM) block initialization on hardware.
* **HIL Report Parser (`/backend/app/tasks`):** Parses Vivado reports for setup Worst Negative Slack (WNS), dynamic power consumption, and hardware utilization statistics.
* **Database Cache:** Local DuckDB cache for tracking processed patient records and synthesis logs.

### 2. Analytics Dashboard UI (`/pulse-analytics`)
A premium, responsive React dashboard built with TanStack Start, Vite, Tailwind CSS, Framer Motion, and Recharts:
* **Workspace Overview:** Displays active patient statistics, arrhythmia anomalies, and pipeline state.
* **MATLAB Upload:** Drag-and-drop workspace uploader supporting `.mat`, `.hea`, and `.atr` telemetry files, featuring single-click Demo Patient Data synchronization.
* **ECG Signal Analysis:** Interactive, high-performance visualizer showing raw signals, segmented heartbeats, R-peaks, and Z-score normalized curves.
* **AI Prediction & CNN Visualization:** Visualizes dynamic feature activation maps (weights/biases) across individual 1D convolutional layers.
* **Model Optimization (Quantization & HEX):** Visualizes FP32 weight distribution compressing to dynamic INT8 formats with clock-level resource and footprint comparisons.
* **FPGA Synthesis Dashboard:** Displays timing margins (WNS/TNS), resources (LUTs, FFs, BRAM, DSPs), and on-chip thermal dissipation.

---

## 🚀 Getting Started & Execution

### Prerequisites
* **Python 3.10+** (with virtual environment support)
* **Node.js 18+**
* **Docker / Docker-Compose** (optional, for containerized deployment)

### 1. Spin Up the Backend API
Navigate to the backend directory, install requirements, and run the FastAPI server:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Spin Up the Frontend Dashboard
Navigate to the analytics folder, install dependencies, and start the Vite development server:
```bash
cd pulse-analytics
npm install
npm run dev -- --port 8081
```
Open **`http://localhost:8081/dashboard`** in your browser.

---

## 🛠️ Key Pipeline Stages

1. **Upload Phase:** Upload clinical ECG records (MATLAB format) or select "Load Demo Patient Data" to mock-load standard datasets.
2. **Inference Phase:** Run the 1D-CNN model to categorize heartbeats into ANSI/AAMI EC57 classes.
3. **Quantization Phase:** Execute the FP32 $\to$ INT8 compression pipeline to optimize weight footprints for hardware blocks.
4. **FPGA Synthesis Upload:** Upload Vivado reports (`timing.rpt`, `power.rpt`, `utilization.rpt`) to analyze hardware timing, power budgets, and resource utilization.
5. **Final Validation:** Verify system-level compliance, latency per beat, and overall diagnostic accuracy scorecards.

---

## 🔬 Scientific Formulations Included in the Research Paper
* **Z-Score Amplitude Normalization:** $\bar{x}_i = \frac{x_i - \mu}{\sigma + \epsilon}$
* **Kaiser-Window Resampler:** Downsamples high-resolution signals using polyphase interpolation filters.
* **Weight Quantization Mapping:** $W_{\text{int8}} = \text{clip}\left(\text{round}\left(\frac{W_{\text{float}}}{S}\right) + Z, -128, 127\right)$
* **WNS Clock Timing Constraint:** $\text{Slack}_{\text{setup}} = T_{\text{required}} - T_{\text{arrival}}$
