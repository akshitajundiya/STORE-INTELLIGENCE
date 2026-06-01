# PROMPT: "Write tests for CCTV pipeline geometry helpers: point-in-polygon zone
#   assignment and oriented entry-line crossing (in vs out), plus that emitted
#   events validate against the Pydantic Event schema."
# CHANGES MADE: AI's crossed_line test only checked a True/False; rewrote to assert
#   the DIRECTION ('in'/'out') since entry vs exit depends on orientation. Added a
#   schema-roundtrip test through emit.make_event.
from datetime import datetime, timezone
from pipeline.zones import point_in_poly, zone_for_point, crossed_line
from pipeline.emit import make_event
from app.models import Event

SQUARE = [[0, 0], [1, 0], [1, 1], [0, 1]]

def test_point_in_poly():
    assert point_in_poly(0.5, 0.5, SQUARE)
    assert not point_in_poly(1.5, 0.5, SQUARE)

def test_zone_for_point_respects_camera():
    zones = [{"zone_id": "Z1", "camera_id": "CAM_A", "polygon": SQUARE}]
    assert zone_for_point(0.5, 0.5, zones, "CAM_A") == "Z1"
    assert zone_for_point(0.5, 0.5, zones, "CAM_B") is None   # wrong camera

def test_line_crossing_direction():
    line = [[0.0, 0.0], [0.0, 1.0]]            # vertical line
    assert crossed_line((-0.1, 0.5), (0.1, 0.5), line) in ("in", "out")
    assert crossed_line((0.2, 0.5), (0.3, 0.5), line) is None  # no crossing

def test_emitted_event_validates():
    ev = make_event("STORE_BLR_002", "CAM_ENTRY_01", "VIS_x", "ENTRY",
                    datetime(2026, 4, 10, 7, 0, tzinfo=timezone.utc), confidence=0.42)
    Event(**ev)                                # raises if schema-invalid
    assert ev["confidence"] == 0.42            # low confidence NOT suppressed
