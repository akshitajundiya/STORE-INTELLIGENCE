# PROMPT: "Given a FastAPI store-analytics API, write tests for /metrics covering:
#   staff are excluded, empty/unknown store returns zeros not null, a store with
#   visitors but no POS rows yields conversion_rate 0.0, and conversion_rate is
#   between 0 and 1."
# CHANGES MADE: AI asserted unique_visitors>0 for the seeded store with a hard-coded
#   44; I replaced it with structural assertions (0<rate<=1, converted<=unique) so the
#   test stays valid if the simulator seed changes. Added the all-staff exclusion case.
import uuid

def test_metrics_seeded_store_is_consistent(client):
    m = client.get("/stores/STORE_BLR_002/metrics").json()
    assert m["unique_visitors"] > 0
    assert 0.0 <= m["conversion_rate"] <= 1.0
    assert m["converted_visitors"] <= m["unique_visitors"]
    assert isinstance(m["avg_dwell_by_zone"], list)

def test_unknown_store_returns_zeros(client):
    m = client.get("/stores/STORE_DOES_NOT_EXIST/metrics").json()
    assert m["unique_visitors"] == 0 and m["conversion_rate"] == 0.0
    assert m["data_confidence"] == "LOW"

def test_staff_excluded(client):
    s = f"STAFFONLY_{uuid.uuid4().hex[:5]}"
    evs = [dict(event_id=str(uuid.uuid4()), store_id=s, camera_id="CAM_FLOOR_01",
                visitor_id=f"VIS_{i}", event_type="ZONE_ENTER", zone_id="GOOD_VIBES",
                timestamp="2026-04-10T08:00:00Z", is_staff=True, confidence=0.9)
           for i in range(4)]
    client.post("/events/ingest", json={"events": evs})
    m = client.get(f"/stores/{s}/metrics").json()
    assert m["unique_visitors"] == 0          # all staff -> no customers

def test_zero_purchase_store(client):
    s = f"NOPOS_{uuid.uuid4().hex[:5]}"
    evs = [dict(event_id=str(uuid.uuid4()), store_id=s, camera_id="CAM_ENTRY_01",
                visitor_id="VIS_a", event_type="ENTRY",
                timestamp="2026-04-10T08:00:00Z", confidence=0.9)]
    client.post("/events/ingest", json={"events": evs})
    m = client.get(f"/stores/{s}/metrics").json()
    assert m["unique_visitors"] == 1 and m["converted_visitors"] == 0
    assert m["conversion_rate"] == 0.0
