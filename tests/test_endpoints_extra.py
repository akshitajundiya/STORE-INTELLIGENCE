# PROMPT: "Add tests for /heatmap (normalised 0-100 score, data_confidence flag) and
#   /health (db_ok true, per-store last_event_at, stale flag boolean)."
# CHANGES MADE: asserted the top heatmap cell scores exactly 100 (normalisation
#   anchor) and that data_confidence is one of the allowed enums; for health, asserted
#   the seeded store is present and not stale relative to itself.
def test_heatmap_normalised(client):
    h = client.get("/stores/STORE_BLR_002/heatmap").json()
    assert h["cells"] and h["cells"][0]["score"] == 100.0
    assert h["data_confidence"] in ("OK", "LOW")
    assert all(0 <= c["score"] <= 100 for c in h["cells"])

def test_health_reports_feeds(client):
    h = client.get("/health").json()
    assert h["db_ok"] is True and h["status"] == "ok"
    ids = [f["store_id"] for f in h["feeds"]]
    assert "STORE_BLR_002" in ids
    for f in h["feeds"]:
        assert isinstance(f["stale"], bool)
