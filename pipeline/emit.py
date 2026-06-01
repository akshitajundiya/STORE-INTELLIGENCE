"""Event construction + emission. Validates against the same Pydantic schema the
API uses (single source of truth) before writing JSONL / POSTing."""
from __future__ import annotations
import json, sys, uuid
from datetime import datetime, timezone
from typing import Optional
sys.path.insert(0, ".")
from app.models import Event, EventMetadata  # reuse the API contract

def make_event(store_id, camera_id, visitor_id, event_type, ts: datetime,
               zone_id=None, dwell_ms=0, is_staff=False, confidence=0.5,
               queue_depth=None, sku_zone=None, session_seq=None) -> dict:
    ev = Event(event_id=str(uuid.uuid4()), store_id=store_id, camera_id=camera_id,
               visitor_id=visitor_id, event_type=event_type,
               timestamp=ts.astimezone(timezone.utc), zone_id=zone_id,
               dwell_ms=dwell_ms, is_staff=is_staff, confidence=round(confidence, 3),
               metadata=EventMetadata(queue_depth=queue_depth, sku_zone=sku_zone,
                                      session_seq=session_seq))
    return json.loads(ev.model_dump_json())

class JsonlWriter:
    def __init__(self, path): self.f = open(path, "w")
    def write(self, ev: dict): self.f.write(json.dumps(ev) + "\n")
    def close(self): self.f.close()
