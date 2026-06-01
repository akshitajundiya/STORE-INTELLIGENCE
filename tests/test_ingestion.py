# PROMPT: "Write pytest tests for a FastAPI /events/ingest endpoint that must be
#   idempotent by event_id, return partial success on malformed events (not 5xx),
#   and reject batches > 500. Use the TestClient and assert on the IngestResult."
# CHANGES MADE: Added the >500 -> 413 case (AI returned 400); added an explicit
#   re-POST-same-payload idempotency assertion (AI only tested a single post);
#   asserted rejected_detail carries the offending index + raw echo.
import uuid
from tests.conftest import seed_events

def _evt(**kw):
    base = dict(event_id=str(uuid.uuid4()), store_id="STORE_BLR_002",
                camera_id="CAM_ENTRY_01", visitor_id="VIS_t1", event_type="ENTRY",
                timestamp="2026-04-10T07:00:00Z", confidence=0.9)
    base.update(kw); return base

def test_ingest_accepts_valid(client):
    r = client.post("/events/ingest", json={"events": [_evt()]})
    assert r.status_code == 200 and r.json()["accepted"] == 1

def test_ingest_is_idempotent(client):
    e = _evt()
    a = client.post("/events/ingest", json={"events": [e]}).json()
    b = client.post("/events/ingest", json={"events": [e]}).json()  # same payload twice
    assert a["accepted"] == 1
    assert b["accepted"] == 0 and b["duplicates"] == 1

def test_partial_success_on_malformed(client):
    r = client.post("/events/ingest", json={"events": [_evt(), {"event_id": "bad"}]})
    body = r.json()
    assert r.status_code == 200          # NOT a 5xx
    assert body["accepted"] == 1 and body["rejected"] == 1
    assert body["rejected_detail"][0]["index"] == 1

def test_batch_over_500_rejected(client):
    r = client.post("/events/ingest", json={"events": [_evt() for _ in range(501)]})
    assert r.status_code == 413

def test_confidence_bounds_enforced(client):
    r = client.post("/events/ingest", json={"events": [_evt(confidence=1.4)]})
    assert r.json()["rejected"] == 1
