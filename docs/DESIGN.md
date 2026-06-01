# DESIGN — Store Intelligence

## 1. System overview

```
CCTV clips ──> pipeline/detect.py ──> events.jsonl ──> POST /events/ingest ──> SQLite
   (5 cams)     YOLOv8 + ByteTrack      (schema)         (idempotent)            │
                + Re-ID + zones                                                  ▼
                                              GET /metrics /funnel /heatmap /anomalies /health
                                                                  │
                                              dashboard/index.html (live, polls /metrics)
```

The system is two decoupled halves joined by **one contract** — the `Event`
schema in `app/models.py`. The detection half (any language, any GPU box)
produces events; the API half (FastAPI + SQLite, containerised) consumes them.
`pipeline/replay.py` streams a JSONL file into the API at simulated real time,
which is what drives the live dashboard and proves the two halves are genuinely
connected rather than batch-coupled.

The single business metric everything serves is **Offline Conversion Rate =
converted visitors ÷ unique visitors**. Every design choice below is judged by
whether it makes that number more *accurate* (detection side) or more
*actionable* (API side).

## 2. The two hard problems and how the design attacks them

**Re-entry inflation.** A customer who steps out and returns must not become two
visitors. We solve it in two places. In the pipeline, an appearance gallery
(`pipeline/tracker.py`) matches a re-appearing person to a recently-exited one
and emits `REENTRY` reusing the *same* `visitor_id`. In the API, sessions are
keyed by `visitor_id` (`app/sessions.py`), so even if Re-ID misses, the funnel
and unique-visitor counts collapse on the visit token rather than on raw events.
Two layers, because Re-ID on blurred-face CCTV is unreliable and the metric must
degrade gracefully, not silently double-count.

**POS correlation without identity.** There is no `customer_id`. A visitor is
credited as converted only if they were in the billing zone within the store's
correlation window (300 s, from `store_layout.json`) *before* a POS timestamp,
and each transaction maps to at most one visitor (`app/correlation.py`). On the
real 10-Apr Brigade Road data this yields 24 conversions against 24 invoices and
a 54.5% conversion rate on the seeded stream.

## 3. Production posture

Structured JSON logs (`trace_id`, `store_id`, `endpoint`, `latency_ms`,
`event_count`, `status_code`) on every request via middleware. Ingest is
idempotent on `event_id` (`INSERT OR IGNORE`), so a retried batch is safe.
A simulated DB outage (`db._FAIL`) returns a structured **503** with no stack
trace. Zero-traffic and unknown stores return zeroed JSON, never null or a crash.

## 4. AI-Assisted Decisions

1. **Tracker choice — agreed.** I asked an LLM to compare ByteTrack, DeepSORT and
   StrongSORT+OSNet for crowded retail CCTV. It recommended ByteTrack for its
   detection-confidence-based association (good under partial occlusion) and zero
   separate Re-ID model. I agreed for the per-camera tracking, but **overrode**
   the implication that ByteTrack alone solves re-entry — it gives per-camera
   `track_id`, not cross-visit identity, so I added the appearance gallery on top.

2. **Funnel dedupe unit — overrode.** The LLM's first funnel draft counted
   `ENTRY` events. That re-inflates on re-entry. I overrode it to count *sessions*
   (distinct `visitor_id`) and to let a person reach a stage if any of their
   sessions did. The re-entry test in `tests/test_funnel.py` pins this.

3. **Staff detection — agreed with a caveat.** I asked whether to use a VLM to
   read uniforms. The model said a VLM would help but flagged latency/cost and
   face-blur. I agreed to keep VLM *optional* and make the default a rule-based
   heuristic (behind-counter + multi-zone ubiquity), which matches the five
   always-present salespeople in the POS export. The VLM prompt and my verdict
   are in CHOICES.md.
