"""GET /health — db status + per-store last event ts + STALE_FEED.
Lag is measured against the freshest feed the system has seen (reference ts), so
a single replayed historical store isn't falsely flagged; a feed that falls >10
min behind the freshest is flagged stale."""
from __future__ import annotations
from datetime import datetime, timezone
from . import db
from .models import HealthResponse, StoreFeedStatus

STALE_SECONDS = 600

def health() -> HealthResponse:
    db_ok = db.healthcheck()
    feeds = []
    if db_ok:
        pairs = db.last_event_epoch_by_store()
        reference = max((ep for _, ep in pairs), default=None)
        for sid, ep in pairs:
            lag = (reference - ep) if (reference and ep) else None
            feeds.append(StoreFeedStatus(
                store_id=sid,
                last_event_at=datetime.fromtimestamp(ep, tz=timezone.utc) if ep else None,
                lag_seconds=round(lag, 1) if lag is not None else None,
                stale=bool(lag is not None and lag > STALE_SECONDS)))
    return HealthResponse(status="ok" if db_ok else "degraded", db_ok=db_ok,
                          feeds=feeds, generated_at=datetime.now(timezone.utc))
