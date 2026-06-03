"""Ingest: validate each event independently (partial success), then idempotent
bulk insert (dedupe by event_id via INSERT OR IGNORE in db.insert_events).

Accepts BOTH our native event schema and the challenge's official
sample_events.jsonl schema (lowercase event_type, id_token, event_timestamp,
store_code, etc.) via a tolerant normaliser, so a reviewer can POST either
format without triggering a 5xx."""
from __future__ import annotations
import uuid as _uuid
from typing import Any, Dict, List
from pydantic import BaseModel, ValidationError
from . import db
from .models import Event, IngestResult, IngestRejected

MAX_BATCH = 500

# Map the official lowercase event types onto our schema's enum.
_TYPE_MAP = {
    "entry": "ENTRY", "exit": "EXIT",
    "zone_entered": "ZONE_ENTER", "zone_exited": "ZONE_EXIT",
    "zone_dwell": "ZONE_DWELL",
    "queue_completed": "BILLING_QUEUE_JOIN",
    "queue_abandoned": "BILLING_QUEUE_ABANDON",
    "reentry": "REENTRY",
}


def _normalize(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Return the event in our schema. If it already matches ours, pass it
    through untouched; otherwise map the official sample_events fields onto ours."""
    if "visitor_id" in raw and str(raw.get("event_type", "")).isupper():
        return raw  # already our native schema

    et = str(raw.get("event_type", "")).strip().lower()
    mapped_type = _TYPE_MAP.get(et, raw.get("event_type"))
    store = raw.get("store_id") or raw.get("store_code")
    visitor = raw.get("visitor_id") or raw.get("id_token") or raw.get("track_id")
    if visitor is not None: visitor = str(visitor)
    ts = (raw.get("timestamp") or raw.get("event_timestamp") or raw.get("event_time")
          or raw.get("queue_join_ts") or raw.get("queue_served_ts") or raw.get("queue_exit_ts"))
    zone = raw.get("zone_id") or raw.get("zone_name")
    cam = str(raw.get("camera_id") or "CAM_UNKNOWN")
    if store is not None: store = str(store)

    eid = raw.get("event_id") or raw.get("queue_event_id")
    if not eid:  # official events have no event_id -> derive a stable one (keeps idempotency)
        eid = str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"{store}|{visitor}|{mapped_type}|{ts}|{zone}"))

    dwell = raw.get("dwell_ms")
    if dwell is None and raw.get("wait_seconds") is not None:
        dwell = int(float(raw["wait_seconds"]) * 1000)

    return {
        "event_id": eid,
        "store_id": store,
        "camera_id": cam,
        "visitor_id": visitor,
        "event_type": mapped_type,
        "timestamp": ts,
        "zone_id": zone,
        "dwell_ms": dwell or 0,
        "is_staff": bool(raw.get("is_staff", False)),
        "confidence": raw.get("confidence", 0.5),
        "metadata": {
            "queue_depth": raw.get("queue_position_at_join") or raw.get("queue_depth"),
            "sku_zone": zone,
            "session_seq": raw.get("session_seq"),
        },
    }


class IngestBody(BaseModel):
    events: List[Dict[str, Any]]


def ingest_events(raw_events: List[Dict[str, Any]]) -> IngestResult:
    valid: List[Event] = []
    rejected: List[IngestRejected] = []
    for i, raw in enumerate(raw_events):
        try:
            valid.append(Event(**_normalize(raw)))
        except ValidationError as e:
            rejected.append(IngestRejected(index=i, error=e.errors()[0]["msg"] if e.errors() else str(e), raw=raw))
        except Exception as e:
            rejected.append(IngestRejected(index=i, error=str(e), raw=raw))
    accepted, duplicates = db.insert_events(valid)
    return IngestResult(accepted=accepted, duplicates=duplicates,
                        rejected=len(rejected), rejected_detail=rejected)