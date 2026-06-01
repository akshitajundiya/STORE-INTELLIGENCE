"""GET /stores/{id}/anomalies — queue spike, conversion drop vs baseline, dead zone.
Each carries severity (INFO/WARN/CRITICAL) + a suggested_action. Conversion-drop
degrades to INFO when <7 days of history exist (single-day dataset) rather than
firing a false CRITICAL."""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from . import db
from .layout import LAYOUT
from .sessions import build_sessions
from .correlation import converted_visitors
from .models import AnomaliesResponse, Anomaly

QUEUE_SPIKE = 5
DEAD_ZONE_MIN = 30
DROP_PCT = 0.30

def _conv_rate(store_id, start_ep, end_ep, billing, window_s):
    rows = db.fetch_events(store_id, start_ep, end_ep, include_staff=False)
    sessions = build_sessions(rows, billing)
    if not sessions:
        return None
    return len(converted_visitors(store_id, sessions, start_ep, end_ep, window_s)) / len(sessions)

def detect_anomalies(store_id, start_ep, end_ep) -> AnomaliesResponse:
    lay = LAYOUT.get(store_id)
    billing = lay.billing_zone_id if lay else "BILLING"
    window_s = lay.pos_correlation_window_seconds if lay else 300
    now = datetime.now(timezone.utc)
    out = []

    rows = db.fetch_events(store_id, start_ep, end_ep, include_staff=False)

    # 1) Queue spike
    depths = [r["queue_depth"] for r in rows if r["queue_depth"] is not None]
    if depths and max(depths) >= QUEUE_SPIKE:
        d = max(depths)
        out.append(Anomaly(type="BILLING_QUEUE_SPIKE",
            severity="CRITICAL" if d >= 8 else "WARN", zone_id=billing,
            detail=f"Billing queue depth reached {d}.",
            suggested_action="Open a second counter / route a floor associate to checkout.",
            detected_at=now))

    # 2) Conversion drop vs trailing baseline (up to 7 prior days)
    today = _conv_rate(store_id, start_ep, end_ep, billing, window_s)
    base_rates = []
    for i in range(1, 8):
        s, e = start_ep - i*86400, end_ep - i*86400
        r = _conv_rate(store_id, s, e, billing, window_s)
        if r is not None:
            base_rates.append(r)
    if today is not None and base_rates:
        base = sum(base_rates)/len(base_rates)
        if base > 0 and today < base*(1-DROP_PCT):
            out.append(Anomaly(type="CONVERSION_DROP",
                severity="INFO" if len(base_rates) < 7 else "WARN", zone_id=None,
                detail=f"Conversion {today:.1%} vs {len(base_rates)}-day baseline {base:.1%}.",
                suggested_action="Audit floor staffing in high-dwell low-buy zones.",
                detected_at=now))

    # 3) Dead zone — known display zone with no visits in last 30 min of activity
    if rows and lay:
        last = max(r["ts_epoch"] for r in rows)
        cutoff = last - DEAD_ZONE_MIN*60
        recent = {r["zone_id"] for r in rows if r["zone_id"] and r["ts_epoch"] >= cutoff}
        display = {z["zone_id"] for z in lay.zones
                   if z.get("type") in ("shelf", "engagement", "feature")}
        for z in sorted(display - recent):
            out.append(Anomaly(type="DEAD_ZONE", severity="INFO", zone_id=z,
                detail=f"No visits to {z} in last {DEAD_ZONE_MIN} min.",
                suggested_action=f"Spotlight {z} or station a promoter; check planogram.",
                detected_at=now))

    return AnomaliesResponse(store_id=store_id, anomalies=out)
