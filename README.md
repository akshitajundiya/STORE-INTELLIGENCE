# Store Intelligence — CCTV → Live Conversion Analytics

Turns raw store CCTV into the one number offline retail is blind to:
**Offline Conversion Rate**. Detection pipeline → event stream → FastAPI
intelligence API → live dashboard. Built and validated on the real Brigade Road
(Bangalore) floor plan + 10-Apr POS export (store `STORE_BLR_002`).

## Quickstart (5 commands)

```bash
git clone <repo> && cd store-intelligence
docker compose up --build            # API on :8000, dashboard on :8080
curl localhost:8000/health
curl localhost:8000/stores/STORE_BLR_002/metrics
open http://localhost:8080           # live dashboard
```

On startup the API seeds `data/sample_events.jsonl` so every endpoint returns
real, computed values immediately — no manual step before the gate checks.

## Run the detection pipeline on the CCTV clips

The CV deps are heavy and run on your machine, not in the API container:

```bash
pip install ultralytics supervision opencv-python-headless numpy
# put the 5 .mp4 clips in ./clips  (CAM 1..5 -> entry/floor/billing by file_hint)
bash pipeline/run.sh ./clips STORE_BLR_002      # -> data/events.jsonl
python -m pipeline.replay --events data/events.jsonl --api http://localhost:8000 --speed 60
```

`detect.py` runs YOLOv8 + ByteTrack, crosses a virtual entry line for ENTRY/EXIT,
maps foot-points to zone polygons (`store_layout.json`) for ZONE_*/dwell, tracks
billing occupancy for queue events, flags staff, and re-IDs returners as REENTRY.
Output validates against the same Pydantic schema the API ingests.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/events/ingest` | batch ≤500, idempotent by `event_id`, partial success |
| GET | `/stores/{id}/metrics` | unique visitors, conversion, dwell/zone, queue, abandonment |
| GET | `/stores/{id}/funnel` | Entry→Zone→Billing→Purchase, session-based, drop-off % |
| GET | `/stores/{id}/heatmap` | zone visit freq + dwell, normalised 0–100 |
| GET | `/stores/{id}/anomalies` | queue spike / conversion drop / dead zone + suggested_action |
| GET | `/health` | db status, per-store last-event ts, STALE_FEED |

`?date=YYYY-MM-DD` overrides the default window (the store's latest event day).

## Tests

```bash
pip install -r requirements.txt pytest pytest-cov
pytest            # 26 tests, ~93% coverage on app + pipeline logic
```

Covers idempotency, partial-success ingest, staff exclusion, zero-purchase,
re-entry dedupe, queue-spike anomaly, DB-unavailable→503, and pipeline geometry.

## Dashboard (Part E)

`dashboard/index.html` polls `/metrics`, `/funnel`, `/heatmap`, `/anomalies`
every 3 s. With `replay.py` streaming events, the conversion rate, funnel and
queue update live — local URL **http://localhost:8080**.

## Layout & repo notes

- `app/` FastAPI + SQLite (see `docs/CHOICES.md` for the Postgres path).
- `pipeline/` detection (`detect.py`, `tracker.py`, `zones.py`, `staff.py`,
  `emit.py`), real-time `replay.py`, and `simulate.py` (CI/demo event generator).
- `data/store_layout.json` — Brigade Road zones (north skincare wall, south
  makeup wall, central FOH/makeup units, cash counter), polygons normalised
  0–1 per camera; recalibrate to your frames before a production run.
- `docs/DESIGN.md`, `docs/CHOICES.md`, `docs/DATA_ANALYSIS.md`, `docs/SCORING_MATRIX.md`.
