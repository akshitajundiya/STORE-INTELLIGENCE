"""
app/sessions.py — reconstruct per-visitor sessions from the raw event stream.

The unit of analysis is the physical visitor (visitor_id), NOT the raw event and
NOT the entry/exit cycle. A returning customer produces a REENTRY event with the
SAME visitor_id, so collapsing by visitor_id is what kills the "re-entry
inflation" problem. Staff (is_staff=1) are excluded upstream in db.fetch_events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Session:
    visitor_id: str
    entered: bool = False
    reentries: int = 0
    zones_visited: set = field(default_factory=set)
    zone_dwell_ms: Dict[str, int] = field(default_factory=dict)
    joined_billing_queue: bool = False
    abandoned_queue: bool = False
    first_epoch: Optional[float] = None
    last_epoch: Optional[float] = None
    billing_epochs: List[float] = field(default_factory=list)
    purchased: bool = False


def build_sessions(rows, billing_zone_id: str) -> Dict[str, Session]:
    sessions: Dict[str, Session] = {}
    for r in rows:
        vid = r["visitor_id"]
        s = sessions.get(vid)
        if s is None:
            s = Session(visitor_id=vid)
            sessions[vid] = s

        ep = r["ts_epoch"]
        s.first_epoch = ep if s.first_epoch is None else min(s.first_epoch, ep)
        s.last_epoch = ep if s.last_epoch is None else max(s.last_epoch, ep)

        et = r["event_type"]
        zone = r["zone_id"]
        if et == "ENTRY":
            s.entered = True
        elif et == "REENTRY":
            s.entered = True
            s.reentries += 1
        elif et in ("ZONE_ENTER", "ZONE_DWELL") and zone:
            s.zones_visited.add(zone)
            s.zone_dwell_ms[zone] = max(s.zone_dwell_ms.get(zone, 0), r["dwell_ms"] or 0)
            if zone == billing_zone_id:
                s.billing_epochs.append(ep)
        elif et == "BILLING_QUEUE_JOIN":
            s.joined_billing_queue = True
            s.billing_epochs.append(ep)
        elif et == "BILLING_QUEUE_ABANDON":
            s.abandoned_queue = True
    return sessions
