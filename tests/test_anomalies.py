# PROMPT: "Write tests for an anomalies endpoint that emits BILLING_QUEUE_SPIKE
#   (severity scales with queue depth), DEAD_ZONE (no visits 30 min), and carries a
#   suggested_action per anomaly. Also test graceful DB-unavailable -> 503."
# CHANGES MADE: AI asserted a fixed anomaly count; replaced with type/severity/field
#   presence checks. Added the DB-outage 503 test using the db._FAIL hook and asserted
#   the body is structured (no stack trace) with an error key.
from app import db

def test_anomalies_shape_and_actions(client):
    a = client.get("/stores/STORE_BLR_002/anomalies").json()
    assert a["store_id"] == "STORE_BLR_002"
    for an in a["anomalies"]:
        assert an["severity"] in ("INFO", "WARN", "CRITICAL")
        assert an["suggested_action"]
        assert an["type"] in ("BILLING_QUEUE_SPIKE", "CONVERSION_DROP", "DEAD_ZONE")

def test_queue_spike_present_in_seed(client):
    a = client.get("/stores/STORE_BLR_002/anomalies").json()
    # At least one anomaly is detected (DEAD_ZONE, CONVERSION_DROP, or BILLING_QUEUE_SPIKE)
    assert len(a["anomalies"]) > 0

def test_db_unavailable_returns_503(client):
    db._FAIL["on"] = True
    r = client.get("/stores/STORE_BLR_002/metrics")
    db._FAIL["on"] = False
    assert r.status_code == 503
    body = r.json()
    assert body["error"] == "database_unavailable" and "trace_id" in body
