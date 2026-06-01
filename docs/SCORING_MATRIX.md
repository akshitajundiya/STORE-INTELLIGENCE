# Scoring Matrix — criterion → artifact

| Part | Criterion (pts) | Where it's satisfied |
|---|---|---|
| A | Entry/exit accuracy (10) | `pipeline/detect.py` virtual entry-line crossing on the entry cam |
| A | Staff / re-entry / group (10) | `pipeline/staff.py` heuristic; `pipeline/tracker.py` Re-ID gallery → REENTRY same `visitor_id`; per-person detection counts individuals not groups |
| A | Schema compliance (10) | `app/models.py` Pydantic; `pipeline/emit.py` validates before write; uuid4 ids, ISO-8601, confidence never suppressed |
| B | API correctness (20) | `app/metrics.py`, `funnel.py` — verified via TestClient, real varying outputs |
| B | Funnel + dedupe (10) | `app/funnel.py` session-based; `tests/test_funnel.py::test_reentry_not_double_counted` |
| B | Anomaly correctness (5) | `app/anomalies.py` queue spike / conversion drop / dead zone + severity + suggested_action |
| C | Docker + README (5, gate) | `docker-compose.yml`, `Dockerfile`, 5-command README |
| C | Logs + health (5) | `app/logging_mw.py` (trace_id/latency/event_count/status), `app/health.py` STALE_FEED |
| C | Tests + edge cases (10) | 26 tests, ~93% coverage; empty/all-staff/zero-purchase/re-entry/DB-down |
| D | AI usage depth (15) | `# PROMPT/# CHANGES MADE` in every test; `DESIGN.md` AI-Assisted Decisions; `CHOICES.md` 3 decisions + VLM prompt & verdict |
| E | Live dashboard (+10) | `dashboard/index.html` + `pipeline/replay.py` real-time stream |

## Acceptance gate
1. `docker compose up` — single command, seeds data on startup ✓
2. `/stores/STORE_BLR_002/metrics` returns valid JSON ✓
3. detection pipeline produces structured events (`detect.py` → JSONL) ✓
4. ingest accepts events without 5xx (partial success on bad ones) ✓
5. DESIGN.md (547 w) + CHOICES.md (584 w) ✓
