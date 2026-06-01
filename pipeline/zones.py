"""Geometry: map a point (normalised image coords) to a named zone via
point-in-polygon. Polygons come from store_layout.json, per camera."""
from __future__ import annotations
from typing import List, Optional

def point_in_poly(x: float, y: float, poly: List[List[float]]) -> bool:
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]; xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def zone_for_point(x: float, y: float, zones: List[dict], camera_id: str) -> Optional[str]:
    for z in zones:
        if z.get("camera_id") == camera_id and "polygon" in z and point_in_poly(x, y, z["polygon"]):
            return z["zone_id"]
    return None

def crossed_line(prev, cur, line) -> Optional[str]:
    """Return 'in' / 'out' if segment prev->cur crosses the oriented entry line."""
    (x1, y1), (x2, y2) = line
    def side(px, py): return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
    s_prev, s_cur = side(*prev), side(*cur)
    if s_prev == 0 or s_cur == 0 or (s_prev > 0) == (s_cur > 0):
        return None
    return "in" if s_cur > 0 else "out"
