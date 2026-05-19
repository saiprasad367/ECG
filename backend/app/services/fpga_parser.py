import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# ─── Power Report ─────────────────────────────────────────────────────────────

def parse_power_report(content: str) -> Dict[str, Any]:
    """Parse Vivado power.rpt and extract key metrics."""
    result = {
        "total_power_mw": None,
        "dynamic_power_mw": None,
        "static_power_mw": None,
        "io_power_mw": None,
        "logic_power_mw": None,
        "bram_power_mw": None,
        "dsp_power_mw": None,
        "confidence": "Medium",
        "power_supply_voltage": 1.0,
    }

    def find_float(pattern: str, text: str, group: int = 1) -> Optional[float]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(group).replace(",", ""))
            except Exception:
                pass
        return None

    # Total On-Chip Power
    v = find_float(r"Total On-Chip Power \(W\)\s*\|\s*([\d.]+)", content)
    if v:
        result["total_power_mw"] = round(v * 1000, 2)

    # Dynamic
    v = find_float(r"Dynamic \(W\)\s*\|\s*([\d.]+)", content)
    if v:
        result["dynamic_power_mw"] = round(v * 1000, 2)

    # Device Static
    v = find_float(r"Device Static \(W\)\s*\|\s*([\d.]+)", content)
    if v:
        result["static_power_mw"] = round(v * 1000, 2)

    # IO
    v = find_float(r"I/O\s*\|\s*([\d.]+)", content)
    if v:
        result["io_power_mw"] = round(v * 1000, 2)

    # Logic
    v = find_float(r"(?:Clocks|Logic)\s*\|\s*([\d.]+)", content)
    if v:
        result["logic_power_mw"] = round(v * 1000, 2)

    # BRAM
    v = find_float(r"BRAM\s*\|\s*([\d.]+)", content)
    if v:
        result["bram_power_mw"] = round(v * 1000, 2)

    # DSP
    v = find_float(r"DSP\s*\|\s*([\d.]+)", content)
    if v:
        result["dsp_power_mw"] = round(v * 1000, 2)

    # Confidence
    m = re.search(r"Confidence Level\s*\|\s*(\w+)", content, re.IGNORECASE)
    if m:
        result["confidence"] = m.group(1)

    # Removed demo fallback to enforce real data

    return result


# ─── Timing Report ────────────────────────────────────────────────────────────

def parse_timing_report(content: str) -> Dict[str, Any]:
    result = {
        "clock_period_ns": None,
        "clock_frequency_mhz": None,
        "worst_negative_slack_ns": None,
        "worst_hold_slack_ns": None,
        "total_negative_slack_ns": 0.0,
        "failing_endpoints": 0,
        "setup_violations": 0,
        "hold_violations": 0,
        "timing_met": True,
    }

    def find_float(pattern, text, group=1):
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(group))
            except Exception:
                pass
        return None

    # Slack
    v = find_float(r"WNS\(ns\)\s*[\|\s]+([-\d.]+)", content)
    if v is not None:
        result["worst_negative_slack_ns"] = v
        result["timing_met"] = v >= 0

    # TNS
    v = find_float(r"TNS\(ns\)\s*[\|\s]+([-\d.]+)", content)
    if v is not None:
        result["total_negative_slack_ns"] = v

    # Failing paths
    v = find_float(r"TNS Failing Endpoints\s*[\|\s]+(\d+)", content)
    if v is not None:
        result["failing_endpoints"] = int(v)
        result["setup_violations"] = int(v)

    # Period
    v = find_float(r"Period\(ns\)\s*[\|\s]+([\d.]+)", content)
    if v:
        result["clock_period_ns"] = v
        result["clock_frequency_mhz"] = round(1000 / v, 2)

    # Removed demo fallback to enforce real data
    return result


# ─── Utilization Report ───────────────────────────────────────────────────────

def parse_utilization_report(content: str) -> Dict[str, Any]:
    result = {}

    def find_used_avail(resource_pattern: str, text: str):
        m = re.search(resource_pattern, text, re.IGNORECASE | re.MULTILINE)
        if m:
            try:
                used = float(m.group(1).replace(",", ""))
                avail = float(m.group(2).replace(",", ""))
                pct = round(used / avail * 100, 2) if avail > 0 else 0
                return {"used": used, "available": avail, "percentage": pct}
            except Exception:
                pass
        return None

    # LUTs
    v = find_used_avail(r"Slice LUTs\s*\|\s*([\d,]+)\s*\|\s*\d+\s*\|\s*([\d,]+)", content)
    if v:
        result["lut"] = v

    # FFs
    v = find_used_avail(r"Slice Registers\s*\|\s*([\d,]+)\s*\|\s*\d+\s*\|\s*([\d,]+)", content)
    if v:
        result["flip_flops"] = v

    # BRAM
    v = find_used_avail(r"Block RAM Tile\s*\|\s*([\d.]+)\s*\|\s*\d+\s*\|\s*([\d.]+)", content)
    if v:
        result["bram_tile"] = v

    # DSP
    v = find_used_avail(r"DSPs\s*\|\s*([\d,]+)\s*\|\s*\d+\s*\|\s*([\d,]+)", content)
    if v:
        result["dsp"] = v

    # IO
    v = find_used_avail(r"Bonded IOB\s*\|\s*([\d,]+)\s*\|\s*\d+\s*\|\s*([\d,]+)", content)
    if v:
        result["io"] = v

    # Removed demo fallback to enforce real data
    return result


# ─── Main entry point ─────────────────────────────────────────────────────────

def parse_all_reports(power_content: str, timing_content: str, util_content: str) -> Dict[str, Any]:
    power = parse_power_report(power_content)
    timing = parse_timing_report(timing_content)
    utilization = parse_utilization_report(util_content)

    # Derive performance estimates
    freq_mhz = timing.get("clock_frequency_mhz") or 100.0
    latency_cycles = 152
    latency_us = round(latency_cycles / freq_mhz, 3)
    throughput = round(1_000_000 / (latency_us * 1000), 0) if latency_us > 0 else 0

    return {
        "power_analysis": power,
        "timing_analysis": timing,
        "utilization": utilization,
        "performance": {
            "latency_cycles": latency_cycles,
            "latency_us": latency_us,
            "throughput_beats_per_second": int(throughput),
            "efficiency": "High" if freq_mhz >= 100 else "Medium",
        },
        "device_info": {
            "family": "Zynq-7000",
            "device": "xc7z020clg484-1",
            "speed_grade": "-1",
        },
    }
