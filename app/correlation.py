"""POS correlation: credit a visitor as converted if they were present in the
billing zone within `window_seconds` BEFORE a POS transaction. Each transaction
maps to at most one visitor (most recent qualifying billing presence)."""
from __future__ import annotations
from typing import Dict
from . import db
from .sessions import Session

def converted_visitors(store_id: str, sessions: Dict[str, Session],
                       start_ep: float, end_ep: float, window_s: int) -> set:
    txns = db.fetch_pos(store_id, start_ep, end_ep)
    converted, used = set(), set()
    for t in txns:
        t_ep = t["ts_epoch"]
        lo = t_ep - window_s
        best, best_ep = None, -1.0
        for vid, s in sessions.items():
            if vid in used:
                continue
            for be in s.billing_epochs:
                if lo <= be <= t_ep and be > best_ep:
                    best, best_ep = vid, be
        if best:
            converted.add(best); used.add(best)
            sessions[best].purchased = True
    return converted
