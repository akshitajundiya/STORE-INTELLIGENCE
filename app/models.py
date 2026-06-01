"""
app/models.py — Pydantic schema for the event stream and API responses.

The Event model is the single contract between the detection pipeline (producer)
and the Intelligence API (consumer). It is validated on ingest; malformed events
are rejected per-event (partial success), not by failing the whole batch.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, field_validator


class EventType(str, enum.Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"


class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: Optional[int] = None
    bbox: Optional[List[float]] = None
    track_id: Optional[int] = None
    reid_score: Optional[float] = None
    model_config = {"extra": "allow"}


class Event(BaseModel):
    event_id: str = Field(..., description="UUID v4 — idempotency key")
    store_id: str
    camera_id: str
    visitor_id: str = Field(..., description="Re-ID token, unique per visit session")
    event_type: EventType
    timestamp: datetime = Field(..., description="ISO-8601 UTC")
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float = Field(..., ge=0.0, le=1.0)
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    @field_validator("event_id")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("event_id must be non-empty")
        return v


class IngestRejected(BaseModel):
    index: int
    error: str
    raw: Dict[str, Any]


class IngestResult(BaseModel):
    accepted: int
    duplicates: int
    rejected: int
    rejected_detail: List[IngestRejected] = []


class ZoneDwell(BaseModel):
    zone_id: str
    avg_dwell_ms: float
    sessions: int


class MetricsResponse(BaseModel):
    store_id: str
    window_start: datetime
    window_end: datetime
    unique_visitors: int
    converted_visitors: int
    conversion_rate: float
    avg_dwell_by_zone: List[ZoneDwell]
    current_queue_depth: int
    abandonment_rate: float
    data_confidence: str
    generated_at: datetime


class FunnelStage(BaseModel):
    stage: str
    visitors: int
    drop_off_pct: float


class FunnelResponse(BaseModel):
    store_id: str
    sessions: int
    stages: List[FunnelStage]
    data_confidence: str


class HeatmapCell(BaseModel):
    zone_id: str
    visit_frequency: int
    avg_dwell_ms: float
    score: float


class HeatmapResponse(BaseModel):
    store_id: str
    cells: List[HeatmapCell]
    data_confidence: str


class Anomaly(BaseModel):
    type: str
    severity: str
    zone_id: Optional[str] = None
    detail: str
    suggested_action: str
    detected_at: datetime


class AnomaliesResponse(BaseModel):
    store_id: str
    anomalies: List[Anomaly]


class StoreFeedStatus(BaseModel):
    store_id: str
    last_event_at: Optional[datetime]
    lag_seconds: Optional[float]
    stale: bool


class HealthResponse(BaseModel):
    status: str
    db_ok: bool
    feeds: List[StoreFeedStatus]
    generated_at: datetime
