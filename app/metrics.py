"""GET /stores/{id}/metrics — unique visitors, conversion, dwell, queue, abandonment.
Staff excluded at the DB layer. Zero-traffic / zero-purchase handled explicitly."""
from __future__ import annotations
from datetime import datetime, timezone
from . import db
from .layout import LAYOUT
from .sessions import build_sessions
from .correlation import converted_visitors
from .models import MetricsResponse, ZoneDwell

def compute_metrics(store_id, start_ep, end_ep, start_dt, end_dt) -> MetricsResponse:
    lay = LAYOUT.get(store_id)
    billing = lay.billing_zone_id if lay else "BILLING"
    window_s = lay.pos_correlation_window_seconds if lay else 300

    rows = db.fetch_events(store_id, start_ep, end_ep, include_staff=False)
    sessions = build_sessions(rows, billing)
    unique = len(sessions)
    converted = converted_visitors(store_id, sessions, start_ep, end_ep, window_s)
    conv_rate = round(len(converted) / unique, 4) if unique else 0.0

    zone_acc: dict[str, list[int]] = {}
    for s in sessions.values():
        for z, d in s.zone_dwell_ms.items():
            zone_acc.setdefault(z, []).append(d)
    dwell = [ZoneDwell(zone_id=z, avg_dwell_ms=round(sum(v)/len(v), 1), sessions=len(v))
             for z, v in sorted(zone_acc.items())]

    joined = sum(1 for s in sessions.values() if s.joined_billing_queue)
    abandoned = sum(1 for s in sessions.values() if s.abandoned_queue)
    abandon_rate = round(abandoned / joined, 4) if joined else 0.0

    return MetricsResponse(
        store_id=store_id, window_start=start_dt, window_end=end_dt,
        unique_visitors=unique, converted_visitors=len(converted),
        conversion_rate=conv_rate, avg_dwell_by_zone=dwell,
        current_queue_depth=db.latest_queue_depth(store_id, end_ep),
        abandonment_rate=abandon_rate,
        data_confidence="LOW" if unique < 20 else "OK",
        generated_at=datetime.now(timezone.utc))
