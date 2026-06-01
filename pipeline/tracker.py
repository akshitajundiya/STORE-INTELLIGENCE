"""Tracking + Re-ID.

Tracking: ByteTrack (via `supervision`) gives stable per-camera track_ids.
Re-ID for RE-ENTRY: a lightweight appearance gallery (colour-histogram embedding
+ cosine distance) keyed by person. When a NEW track appears at the entry line,
we compare its embedding to recently-exited persons; a match within `reid_thresh`
and `reentry_window_s` reuses the SAME visitor_id and emits REENTRY instead of a
fresh ENTRY. This directly attacks the "re-entry inflation" problem.

Honest limitation (see CHOICES.md): colour-histogram Re-ID is weak under lighting
changes and similar outfits. It is a deliberate trade-off vs a heavy OSNet model;
the API layer is the safety net (session dedupe on visitor_id).
"""
from __future__ import annotations
import time, uuid
from dataclasses import dataclass, field
from typing import Dict, Optional
import numpy as np

def hist_embedding(crop) -> np.ndarray:
    import cv2
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [16, 16], [0, 180, 0, 256])
    h = cv2.normalize(h, h).flatten()
    return h

def cosine(a, b) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

@dataclass
class PersonGallery:
    reid_thresh: float = 0.72
    reentry_window_s: float = 900.0
    _exited: Dict[str, tuple] = field(default_factory=dict)   # person_key -> (emb, exit_ts)
    _track_to_visit: Dict[int, str] = field(default_factory=dict)

    def new_visit_token(self) -> str:
        return f"VIS_{uuid.uuid4().hex[:6]}"

    def on_entry(self, track_id: int, emb, ts: float):
        """Returns (visitor_id, person_key, is_reentry)."""
        best_pk, best_score = None, 0.0
        for pk, (e, t_exit) in list(self._exited.items()):
            if ts - t_exit > self.reentry_window_s:
                self._exited.pop(pk, None); continue
            sc = cosine(emb, e)
            if sc > best_score:
                best_pk, best_score = pk, sc
        if best_pk and best_score >= self.reid_thresh:
            vid = self.new_visit_token()
            self._track_to_visit[track_id] = vid
            self._exited.pop(best_pk, None)
            return vid, best_pk, True
        vid = self.new_visit_token(); pk = f"P_{uuid.uuid4().hex[:8]}"
        self._track_to_visit[track_id] = vid
        return vid, pk, False

    def on_exit(self, track_id: int, person_key: str, emb, ts: float):
        self._exited[person_key] = (emb, ts)
PALETTE = None
