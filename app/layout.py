"""
app/layout.py — loads store_layout.json once and exposes a typed accessor.
Shared by the API (billing zone, correlation window) and the pipeline (zones).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List

LAYOUT_PATH = os.environ.get("LAYOUT_PATH", "/data/store_layout.json")


@dataclass
class StoreLayout:
    store_id: str
    billing_zone_id: str
    entry_zone_id: str
    pos_correlation_window_seconds: int
    zones: List[dict]
    cameras: List[dict]
    open_hours: dict
    staff_roster_hint: List[str]
    raw: dict

    def zone_ids(self) -> List[str]:
        return [z["zone_id"] for z in self.zones]


def _load() -> Dict[str, StoreLayout]:
    out: Dict[str, StoreLayout] = {}
    if not os.path.exists(LAYOUT_PATH):
        return out
    with open(LAYOUT_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    docs = data if isinstance(data, list) else [data]
    for d in docs:
        out[d["store_id"]] = StoreLayout(
            store_id=d["store_id"],
            billing_zone_id=d.get("billing_zone_id", "CASH_COUNTER"),
            entry_zone_id=d.get("entry_zone_id", "ENTRY"),
            pos_correlation_window_seconds=int(d.get("pos_correlation_window_seconds", 300)),
            zones=d.get("zones", []),
            cameras=d.get("cameras", []),
            open_hours=d.get("open_hours", {}),
            staff_roster_hint=d.get("staff_roster_hint", []),
            raw=d,
        )
    return out


LAYOUT: Dict[str, StoreLayout] = _load()


def reload_layout() -> None:
    global LAYOUT
    LAYOUT = _load()
