"""Staff classification.

Primary signal (rule-based, default): ubiquity + behind-counter dwell. A track
that (a) appears behind the billing counter polygon, or (b) visits >= STAFF_ZONE_N
distinct zones within the clip with high cumulative dwell, is flagged staff.
This matches the 5 named salespeople in the POS export who move everywhere.

Optional VLM signal (--use-vlm): crop the person and ask a vision model whether
they wear the store uniform. Prompt + honest verdict documented in CHOICES.md.
Rule-based is the default because uniform cues survive face-blur where a VLM
adds latency/cost for marginal gain on this footage.
"""
from __future__ import annotations
from collections import defaultdict

STAFF_ZONE_N = 6
STAFF_DWELL_MS = 240_000  # 4 min cumulative

class StaffHeuristic:
    def __init__(self, billing_zone_id: str):
        self.billing = billing_zone_id
        self.zones = defaultdict(set)      # person -> {zones}
        self.dwell = defaultdict(int)      # person -> ms
        self.behind_counter = set()

    def observe(self, person_key, zone_id, dwell_ms=0, behind_counter=False):
        if zone_id:
            self.zones[person_key].add(zone_id)
        self.dwell[person_key] += dwell_ms or 0
        if behind_counter:
            self.behind_counter.add(person_key)

    def is_staff(self, person_key) -> bool:
        if person_key in self.behind_counter:
            return True
        return (len(self.zones[person_key]) >= STAFF_ZONE_N
                and self.dwell[person_key] >= STAFF_DWELL_MS)

VLM_STAFF_PROMPT = (
    "You are looking at a cropped image of a single person in a cosmetics retail "
    "store. Their face is blurred for privacy. Answer strictly JSON: "
    '{"is_staff": true|false, "confidence": 0.0-1.0, "cue": "<what you saw>"}. '
    "Staff wear a dark apron over a branded tee and often stand behind the "
    "cash counter. Shoppers carry handbags/baskets and browse shelves."
)
