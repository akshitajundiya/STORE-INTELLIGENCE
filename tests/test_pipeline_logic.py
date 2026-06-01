# PROMPT: "Write unit tests (no video needed) for: a rule-based staff heuristic that
#   flags a person who is behind the billing counter OR ubiquitous across many zones
#   with high dwell; and a Re-ID gallery that reuses the same visitor token (REENTRY)
#   when an exited person reappears within a time window above a similarity threshold."
# CHANGES MADE: AI used random embeddings that flaked; replaced with deterministic
#   identical/orthogonal vectors so the similarity assertions are stable. Added the
#   window-expiry case (a match outside reentry_window_s must NOT be a re-entry).
import numpy as np
from pipeline.staff import StaffHeuristic, STAFF_ZONE_N
from pipeline.tracker import PersonGallery, cosine

def test_staff_behind_counter():
    h = StaffHeuristic("BILLING")
    h.observe("p1", "BILLING", behind_counter=True)
    assert h.is_staff("p1")

def test_staff_ubiquity():
    h = StaffHeuristic("BILLING")
    for i in range(STAFF_ZONE_N):
        h.observe("p2", f"Z{i}", dwell_ms=60_000)
    assert h.is_staff("p2")

def test_shopper_not_staff():
    h = StaffHeuristic("BILLING")
    h.observe("p3", "GOOD_VIBES", dwell_ms=40_000)
    h.observe("p3", "DERMDOC", dwell_ms=20_000)
    assert not h.is_staff("p3")

def test_reid_reentry_match():
    g = PersonGallery(reid_thresh=0.7, reentry_window_s=900)
    emb = np.ones(256, dtype="float32")
    vid, pk, re = g.on_entry(1, emb, ts=0.0); assert not re
    g.on_exit(1, pk, emb, ts=10.0)
    vid2, pk2, re2 = g.on_entry(2, emb, ts=60.0)     # same appearance, soon after
    assert re2 and pk2 == pk and vid2 != vid          # REENTRY: same person, new visit token

def test_reid_window_expiry():
    g = PersonGallery(reid_thresh=0.7, reentry_window_s=300)
    emb = np.ones(256, dtype="float32")
    _, pk, _ = g.on_entry(1, emb, ts=0.0)
    g.on_exit(1, pk, emb, ts=10.0)
    _, _, re = g.on_entry(2, emb, ts=10_000.0)        # returns far too late
    assert not re

def test_cosine_orthogonal():
    a = np.array([1.0, 0.0]); b = np.array([0.0, 1.0])
    assert abs(cosine(a, b)) < 1e-6
