"""Window resolution: default to the day of the store's latest event (the
dataset is single-day); allow ?date=YYYY-MM-DD override. Returns epoch bounds
(for SQL) and tz-aware datetimes (for response models)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone, date as date_cls
from . import db

def resolve_window(store_id: str, day: str | None):
    if day:
        d = date_cls.fromisoformat(day)
    else:
        d = None
        for sid, last in db.last_event_epoch_by_store():
            if sid == store_id and last:
                d = datetime.fromtimestamp(last, tz=timezone.utc).date()
        if d is None:
            d = datetime.now(timezone.utc).date()
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    return start.timestamp(), end.timestamp(), start, end
