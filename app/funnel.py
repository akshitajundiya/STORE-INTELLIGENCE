"""GET /funnel and /heatmap. Funnel is session-based (visitor_id), so re-entries
(same visitor_id) never double-count the top of funnel."""
from __future__ import annotations
from . import db
from .layout import LAYOUT
from .sessions import build_sessions
from .correlation import converted_visitors
from .models import FunnelResponse, FunnelStage, HeatmapResponse, HeatmapCell

def compute_funnel(store_id, start_ep, end_ep) -> FunnelResponse:
    lay = LAYOUT.get(store_id)
    billing = lay.billing_zone_id if lay else "BILLING"
    window_s = lay.pos_correlation_window_seconds if lay else 300
    rows = db.fetch_events(store_id, start_ep, end_ep, include_staff=False)
    sessions = build_sessions(rows, billing)
    converted = converted_visitors(store_id, sessions, start_ep, end_ep, window_s)

    n_entry = sum(1 for s in sessions.values() if s.entered)
    n_zone = sum(1 for s in sessions.values() if s.entered and s.zones_visited)
    n_bill = sum(1 for s in sessions.values() if s.joined_billing_queue)
    n_buy = len(converted)

    def stage(name, n, prev):
        return FunnelStage(stage=name, visitors=n,
                           drop_off_pct=round((1 - n/prev)*100, 1) if prev else 0.0)
    stages = [stage("ENTRY", n_entry, n_entry), stage("ZONE_VISIT", n_zone, n_entry),
              stage("BILLING_QUEUE", n_bill, n_zone), stage("PURCHASE", n_buy, n_bill)]
    return FunnelResponse(store_id=store_id, sessions=len(sessions), stages=stages,
                          data_confidence="LOW" if len(sessions) < 20 else "OK")

def compute_heatmap(store_id, start_ep, end_ep) -> HeatmapResponse:
    lay = LAYOUT.get(store_id)
    billing = lay.billing_zone_id if lay else "BILLING"
    rows = db.fetch_events(store_id, start_ep, end_ep, include_staff=False)
    sessions = build_sessions(rows, billing)
    freq: dict[str, int] = {}
    dwell: dict[str, list[int]] = {}
    for s in sessions.values():
        for z in s.zones_visited:
            freq[z] = freq.get(z, 0) + 1
        for z, d in s.zone_dwell_ms.items():
            dwell.setdefault(z, []).append(d)
    mx = max(freq.values()) if freq else 0
    cells = [HeatmapCell(zone_id=z, visit_frequency=f,
                         avg_dwell_ms=round(sum(dwell.get(z, [0]))/max(len(dwell.get(z, [1])), 1), 1),
                         score=round(f/mx*100, 1) if mx else 0.0)
             for z, f in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)]
    return HeatmapResponse(store_id=store_id, cells=cells,
                           data_confidence="LOW" if len(sessions) < 20 else "OK")
