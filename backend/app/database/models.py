from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class SessionStatus(str, Enum):
    ACTIVE = "active"
    PROCESSING = "processing"
    COMPLETED = "completed"
    EXPIRED = "expired"


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileMetadata(BaseModel):
    filename: str
    size_bytes: int
    storage_path: str
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class MatlabUpload(BaseModel):
    upload_id: str
    files: Dict[str, FileMetadata]
    metadata: Dict[str, Any]
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class VivadoUpload(BaseModel):
    upload_id: str
    files: Dict[str, FileMetadata]
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


class BeatPrediction(BaseModel):
    beat_index: int
    beat_time_seconds: float
    predicted_class: str
    class_id: int
    confidence: float
    probabilities: Dict[str, float]
    is_abnormal: bool
    alert_level: Optional[str] = None


class InferenceResults(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = 0
    task_id: Optional[str] = None
    predictions: Optional[List[Dict]] = None
    summary: Optional[Dict[str, int]] = None
    metrics: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_ms: Optional[int] = None


class QuantizationResults(BaseModel):
    job_id: str
    status: JobStatus
    original_size_mb: Optional[float] = None
    quantized_size_mb: Optional[float] = None
    compression_ratio: Optional[float] = None
    accuracy_fp32: Optional[float] = None
    accuracy_int8: Optional[float] = None
    accuracy_drop: Optional[float] = None
    completed_at: Optional[datetime] = None


class HexGenerationResults(BaseModel):
    job_id: str
    status: JobStatus
    files: Optional[List[Dict]] = None
    download_url: Optional[str] = None
    memory_map: Optional[Dict] = None
    generated_at: Optional[datetime] = None


class FPGAMetrics(BaseModel):
    job_id: str
    status: JobStatus
    power: Optional[Dict[str, Any]] = None
    timing: Optional[Dict[str, Any]] = None
    utilization: Optional[Dict[str, Any]] = None
    performance: Optional[Dict[str, Any]] = None
    device_info: Optional[Dict[str, str]] = None
    parsed_at: Optional[datetime] = None


class Session(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    status: SessionStatus = SessionStatus.ACTIVE
    client_info: Optional[Dict[str, str]] = None
    matlab_upload: Optional[Dict] = None
    vivado_upload: Optional[Dict] = None
    inference: Optional[Dict] = None
    quantization: Optional[Dict] = None
    hex_generation: Optional[Dict] = None
    fpga_analysis: Optional[Dict] = None
