# PROMPT: "Write tests for a session-based conversion funnel endpoint. The funnel
#   stages are ENTRY -> ZONE_VISIT -> BILLING_QUEUE -> PURCHASE and re-entries
#   (same visitor_id) must NOT double-count a visitor at the top of the funnel.
#   Drop-off % must be monotonic-friendly and within [0,100]."
# CHANGES MADE: AI's re-entry test used two different visitor_ids; corrected to reuse
#   the SAME visitor_id with a REENTRY event (that is what our schema specifies) and
#   asserted the funnel still counts ONE visitor.
import uuid

def test_funnel_stages_and_dropoff(client):
    f = client.get("/stores/STORE_BLR_002/funnel").json()
    stages = {s["stage"]: s for s in f["stages"]}
    assert set(stages) == {"ENTRY", "ZONE_VISIT", "BILLING_QUEUE", "PURCHASE"}
    assert stages["PURCHASE"]["visitors"] <= stages["BILLING_QUEUE"]["visitors"]
    for s in f["stages"]:
        assert 0.0 <= s["drop_off_pct"] <= 100.0

def test_reentry_not_double_counted(client):
    s = f"REENTRY_{uuid.uuid4().hex[:5]}"; vid = "VIS_re"
    evs = [
        dict(event_id=str(uuid.uuid4()), store_id=s, camera_id="CAM_ENTRY_01",
             visitor_id=vid, event_type="ENTRY", timestamp="2026-04-10T08:00:00Z", confidence=0.9),
        dict(event_id=str(uuid.uuid4()), store_id=s, camera_id="CAM_ENTRY_01",
             visitor_id=vid, event_type="REENTRY", timestamp="2026-04-10T08:30:00Z", confidence=0.9),
    ]
    client.post("/events/ingest", json={"events": evs})
    f = client.get(f"/stores/{s}/funnel").json()
    assert f["sessions"] == 1     # one visitor despite ENTRY + REENTRY
