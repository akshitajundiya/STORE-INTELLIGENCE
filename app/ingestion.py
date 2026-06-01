"""Ingest: validate each event independently (partial success), then idempotent
bulk insert (dedupe by event_id via INSERT OR IGNORE in db.insert_events)."""
from __future__ import annotations
from typing import Any, Dict, List
from pydantic import BaseModel, ValidationError
from . import db
from .models import Event, IngestResult, IngestRejected

MAX_BATCH = 500

class IngestBody(BaseModel):
    events: List[Dict[str, Any]]

def ingest_events(raw_events: List[Dict[str, Any]]) -> IngestResult:
    valid: List[Event] = []
    rejected: List[IngestRejected] = []
    for i, raw in enumerate(raw_events):
        try:
            valid.append(Event(**raw))
        except ValidationError as e:
            rejected.append(IngestRejected(index=i, error=e.errors()[0]["msg"] if e.errors() else str(e), raw=raw))
        except Exception as e:
            rejected.append(IngestRejected(index=i, error=str(e), raw=raw))
    accepted, duplicates = db.insert_events(valid)
    return IngestResult(accepted=accepted, duplicates=duplicates,
                        rejected=len(rejected), rejected_detail=rejected)
