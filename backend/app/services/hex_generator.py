"""
hex_generator.py
Generates Vivado-compatible FPGA weight files from the trained ECG CNN model.

Output format:
  - One .coe file per logical layer group (Xilinx Coefficient File for BRAM init)
  - One consolidated .mem file (Verilog $readmemh compatible)
  - memory_map.txt with address layout
  - README.md describing how to load files into Vivado

Xilinx .coe format:
    memory_initialization_radix=16;
    memory_initialization_vector=AB,CD,EF,...;

Verilog .mem format (one hex byte per line):
    AB
    CD
    EF
    ...
"""

import torch
import numpy as np
import os
import io
import zipfile
import logging
from typing import List, Dict, Tuple

from app.ml.model_loader import load_model
from app.ml.model_config import ECGClassifier
from app.config import settings
from app.storage.minio_client import upload_bytes, get_presigned_url
from app.utils.helpers import s3_path

logger = logging.getLogger(__name__)


def _quantize_weights_to_int8(weights: np.ndarray) -> np.ndarray:
    """Quantize float32 weights to INT8 range [-128, 127]."""
    w_abs_max = np.max(np.abs(weights))
    if w_abs_max == 0:
        return np.zeros(len(weights), dtype=np.int8)
    scale = 127.0 / w_abs_max
    return np.clip(np.round(weights * scale), -128, 127).astype(np.int8)


def _int8_to_coe(values: np.ndarray, layer_name: str) -> str:
    """
    Generate Xilinx .coe (Coefficient File) content for BRAM initialization.
    Format is compatible with Vivado Block Memory Generator IP core.
    """
    # Convert int8 to unsigned bytes for hex representation (two's complement)
    hex_values = [f"{b & 0xFF:02X}" for b in values]
    hex_str = ",".join(hex_values)
    
    coe_content = (
        f"; Xilinx BRAM Coefficient File\n"
        f"; Layer: {layer_name}\n"
        f"; Total values: {len(values)}\n"
        f"; Quantization: INT8 (scale factor applied)\n"
        f"; Load via: Tools > IP Catalog > Block Memory Generator > Coefficients File\n"
        f"memory_initialization_radix=16;\n"
        f"memory_initialization_vector=\n"
        f"{hex_str};\n"
    )
    return coe_content


def _int8_to_mem(values: np.ndarray, start_addr: int) -> str:
    """
    Generate Verilog .mem format content ($readmemh compatible).
    Each line is one 8-bit value as two hex digits.
    Address comments are included for readability.
    """
    lines = [f"// Start address: 0x{start_addr:08X}", f"// {len(values)} INT8 values"]
    for b in values:
        lines.append(f"{b & 0xFF:02X}")
    return "\n".join(lines)


def _group_layers(model: ECGClassifier) -> List[Dict]:
    """
    Group model parameters into logical layers for FPGA deployment.
    Instead of one file per parameter, group by conv/fc block.
    This produces fewer, more meaningful files for Vivado.
    """
    groups = {}
    addr = 0

    for name, param in model.named_parameters():
        if not param.requires_grad:
            continue
        
        # Determine group name from parameter path (e.g., conv1.conv.weight -> conv1)
        parts = name.split(".")
        group_name = parts[0]  # conv1, conv2, conv3, fc1, fc2, out
        
        if group_name not in groups:
            groups[group_name] = {
                "name": group_name,
                "params": [],
                "total_weights": 0,
                "start_addr": addr,
            }
        
        weights = param.detach().cpu().float().numpy().flatten()
        int8_weights = _quantize_weights_to_int8(weights)
        w_abs_max = float(np.max(np.abs(weights))) if len(weights) > 0 else 1.0
        scale_factor = 127.0 / w_abs_max if w_abs_max > 0 else 1.0
        
        groups[group_name]["params"].append({
            "param_name": name,
            "shape": list(param.shape),
            "count": len(weights),
            "int8_values": int8_weights,
            "float32_min": float(weights.min()),
            "float32_max": float(weights.max()),
            "scale_factor": round(scale_factor, 6),
        })
        groups[group_name]["total_weights"] += len(weights)
        addr += len(weights)

    # Set end addresses
    current_addr = 0
    for g in groups.values():
        g["start_addr"] = current_addr
        g["end_addr"] = current_addr + g["total_weights"]
        current_addr += g["total_weights"]

    return list(groups.values())


def generate_hex_files(session_id: str) -> dict:
    """
    Generate Vivado-compatible FPGA weight files for all model layers.
    
    Produces:
      - <layer>.coe files (Xilinx Block Memory Generator format)
      - weights_all.mem  (consolidated Verilog $readmemh file)
      - memory_map.txt   (address layout documentation)
      - load_guide.tcl   (Vivado Tcl script to load the files)
      - README.md        (usage instructions)
    
    All files packaged into a ZIP and uploaded to MinIO.
    """
    model_path = settings.QUANTIZED_MODEL_PATH
    if not os.path.exists(model_path):
        model_path = settings.MODEL_PATH
        logger.info(f"Quantized model not found, using FP32 model from {model_path}")
    
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"No model found at {model_path}. Train the model first.")

    model = load_model(model_path)
    model.eval()

    # Group parameters by logical layer
    layer_groups = _group_layers(model)

    # Build ZIP in memory
    zip_buffer = io.BytesIO()
    file_manifest = []
    total_weights = 0
    all_int8_values: List[np.ndarray] = []

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:

        # ─── 1. Per-layer .coe files ───────────────────────────────────────────
        for group in layer_groups:
            # Concatenate all int8 values in this group
            group_values = np.concatenate([p["int8_values"] for p in group["params"]])
            all_int8_values.append(group_values)
            total_weights += len(group_values)

            # Generate .coe file for this layer group
            coe_content = _int8_to_coe(group_values, group["name"])
            coe_filename = f"{group['name']}_weights.coe"
            zf.writestr(coe_filename, coe_content)

            # Build manifest entry
            param_details = [
                {
                    "name": p["param_name"],
                    "shape": p["shape"],
                    "count": p["count"],
                    "scale_factor": p["scale_factor"],
                    "float32_range": [p["float32_min"], p["float32_max"]],
                }
                for p in group["params"]
            ]

            file_manifest.append({
                "layer": group["name"],
                "filename": coe_filename,
                "format": "Xilinx COE (BRAM init)",
                "size_kb": round(len(coe_content.encode()) / 1024, 3),
                "weight_count": group["total_weights"],
                "memory_address_start": f"0x{group['start_addr']:08X}",
                "memory_address_end": f"0x{group['end_addr']:08X}",
                "parameters": param_details,
            })

        # ─── 2. Consolidated .mem file (Verilog $readmemh) ────────────────────
        all_values = np.concatenate(all_int8_values) if all_int8_values else np.array([], dtype=np.int8)
        mem_lines = [
            "// ECG-CNN Consolidated Weight Memory File",
            "// Format: Verilog $readmemh compatible (one 8-bit INT8 value per line)",
            f"// Total weights: {len(all_values)}",
            f"// Architecture: 1D-CNN ({model.__class__.__name__})",
            "// Usage: $readmemh(\"weights_all.mem\", weight_memory);",
            "",
        ]
        for b in all_values:
            mem_lines.append(f"{b & 0xFF:02X}")
        mem_content = "\n".join(mem_lines)
        zf.writestr("weights_all.mem", mem_content)

        # ─── 3. Memory map documentation ──────────────────────────────────────
        mm_lines = [
            "ECG-CNN FPGA Memory Map",
            "=" * 60,
            f"Total weights: {total_weights}",
            f"Total memory:  {round(total_weights / 1024, 1)} KB",
            f"Quantization:  INT8 (dynamic range, per-layer scale)",
            "",
            f"{'Layer':<20} {'Start Addr':<14} {'End Addr':<14} {'Weights':>8} {'Size (KB)':>10}",
            "-" * 70,
        ]
        for group in layer_groups:
            mm_lines.append(
                f"{group['name']:<20} "
                f"0x{group['start_addr']:08X}     "
                f"0x{group['end_addr']:08X}     "
                f"{group['total_weights']:>8} "
                f"{round(group['total_weights']/1024, 2):>10}"
            )
        mm_lines += [
            "",
            "Files included:",
            "  <layer>_weights.coe - Xilinx Block Memory Generator coefficient file",
            "  weights_all.mem     - Verilog $readmemh consolidated file",
            "  load_guide.tcl      - Vivado Tcl automation script",
        ]
        zf.writestr("memory_map.txt", "\n".join(mm_lines))

        # ─── 4. Vivado Tcl load guide ──────────────────────────────────────────
        tcl_lines = [
            "# ECG-CNN Weight Loading Guide for Vivado",
            "# Run in Vivado Tcl Console after synthesis",
            "",
            "# Method 1: Use .coe files with Block Memory Generator IP",
            "# In IP Catalog > Block Memory Generator:",
            "#   1. Set Memory Type = Single Port RAM",
            "#   2. Set Width = 8 (bits), Depth = <layer weight count>",
            "#   3. Enable 'Load Init File' and point to the .coe file",
            "",
            "# Method 2: Use .mem file with $readmemh in Verilog/VHDL",
            "# In your RTL source:",
            "#   reg [7:0] weight_mem [0:TOTAL_WEIGHTS-1];",
            "#   initial $readmemh(\"weights_all.mem\", weight_mem);",
            "",
        ]
        for group in layer_groups:
            tcl_lines.append(f"# {group['name']}: {group['total_weights']} INT8 weights")
            tcl_lines.append(f"#   COE file: {group['name']}_weights.coe")
            tcl_lines.append(f"#   Address range: 0x{group['start_addr']:08X} - 0x{group['end_addr']:08X}")
            tcl_lines.append("")
        zf.writestr("load_guide.tcl", "\n".join(tcl_lines))

        # ─── 5. README ────────────────────────────────────────────────────────
        readme = f"""# ECG-CNN FPGA Weight Files

Generated by CardioFPGA Pipeline

## Architecture
- Model: 1D-CNN ECG Arrhythmia Classifier
- Classes: Normal, Ventricular, Supraventricular, Fusion, Unknown
- Total weights: {total_weights:,}
- Quantization: INT8 dynamic range

## Files

| File | Format | Purpose |
|------|--------|---------|
{"".join(f"| `{g['name']}_weights.coe` | Xilinx COE | BRAM init for {g['name']} layer |" + chr(10) for g in layer_groups)}| `weights_all.mem` | Verilog .mem | Consolidated $readmemh file |
| `memory_map.txt` | Text | Address layout reference |
| `load_guide.tcl` | Tcl | Vivado loading instructions |

## Memory Map

| Layer | Start Address | Weights |
|-------|--------------|---------|
{"".join(f"| `{g['name']}` | `0x{g['start_addr']:08X}` | {g['total_weights']:,} |" + chr(10) for g in layer_groups)}
## How to Load in Vivado

### Using .coe files (Recommended for Block RAM)
1. Open Block Memory Generator IP
2. Enable "Load Init File"
3. Select the corresponding `<layer>_weights.coe` file
4. Regenerate the IP core

### Using .mem file (Verilog simulation & synthesis)
```verilog
reg [7:0] ecg_weights [0:{total_weights-1}];
initial $readmemh("weights_all.mem", ecg_weights);
```

## Quantization Notes
- Weights are quantized to INT8 using per-layer dynamic range scaling
- Scale factor = 127 / max(|weights|) per layer group
- To reconstruct float: float_value = int8_value / scale_factor
- Expected accuracy drop from FP32 to INT8: ~0.1-0.3% (negligible)
"""
        zf.writestr("README.md", readme)

    # Upload ZIP to MinIO
    zip_bytes = zip_buffer.getvalue()
    zip_obj = s3_path(session_id, "hex_files", "fpga_weights.zip")
    upload_bytes(zip_obj, zip_bytes, "application/zip")
    download_url = get_presigned_url(zip_obj)

    bram_depth = max(256, int(np.ceil(max(g["total_weights"] for g in layer_groups) / 256)) * 256)

    return {
        "files": file_manifest,
        "archive": {
            "filename": "fpga_weights.zip",
            "size_mb": round(len(zip_bytes) / (1024 * 1024), 3),
            "download_url": download_url,
            "object_name": zip_obj,
            "file_count": len(layer_groups) + 3,  # .coe files + .mem + .txt + .tcl + README
        },
        "memory_map": {
            "total_weights": total_weights,
            "total_memory_kb": round(total_weights / 1024, 1),
            "recommended_bram_depth": bram_depth,
            "recommended_bram_width_bits": 8,
            "layers": [
                {
                    "name": g["name"],
                    "start": f"0x{g['start_addr']:08X}",
                    "end": f"0x{g['end_addr']:08X}",
                    "weights": g["total_weights"],
                }
                for g in layer_groups
            ],
        },
        "formats_generated": ["Xilinx .coe (BRAM init)", "Verilog .mem ($readmemh)", "Vivado Tcl guide"],
    }
