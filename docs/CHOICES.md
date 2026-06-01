# CHOICES — three decisions, with what AI suggested and what I chose

## Decision 1 — Detection + tracking model

**Options considered:** YOLOv8n + ByteTrack · YOLOv9 + DeepSORT · RT-DETR +
StrongSORT/OSNet · MediaPipe.

**What AI suggested:** An LLM ranked StrongSORT+OSNet highest for raw Re-ID
accuracy, ByteTrack second for speed/robustness.

**What I chose and why:** **YOLOv8n + ByteTrack.** The footage is 1080p/15fps
retail CCTV with face blur, so a heavy appearance Re-ID model (OSNet) buys little
— blurred faces and similar outfits defeat it, and it adds a GPU dependency to
every camera. ByteTrack associates even low-confidence boxes, which is exactly
the partial-occlusion edge case (people behind the makeup units / in the billing
crush). For the one thing ByteTrack does *not* do — identity across an
exit/re-entry — I added a cheap colour-histogram gallery rather than a second
deep model. This is a deliberate accuracy-for-simplicity trade: the API's
session dedupe is the backstop if Re-ID misses. **What would change my mind:** if
ground-truth showed re-entry recall below ~70%, I'd swap the histogram for OSNet
embeddings on the entry camera only (one camera, bounded cost).

## Decision 2 — Event schema design

**Options considered:** thin schema (type+timestamp, derive everything later) ·
the rich schema in `app/models.py` (typed enum, `dwell_ms`, `is_staff`,
`confidence`, `metadata.queue_depth/sku_zone/session_seq`).

**What AI suggested:** start thin and enrich later.

**What I chose and why:** the **rich, validated** schema. The schema is the
contract between two teams that never meet; under-specifying it pushes ambiguity
downstream into every metric. Three fields earn their place: `confidence` is
carried, never suppressed, so the API can flag low-confidence data instead of
inheriting silent gaps; `is_staff` is set at the source where behaviour is
visible, so the API can exclude staff with a single `WHERE`; `metadata.queue_depth`
lets `/anomalies` detect a billing spike without re-deriving occupancy. Per-event
Pydantic validation gives partial-success ingest for free — one malformed event
is rejected with its index, the batch still lands.

## Decision 3 — Storage engine for the API

**Options considered:** Postgres · SQLite · in-memory.

**What AI suggested:** Postgres for "production realism."

**What I chose and why:** **SQLite**, accessed through a thin `db.py` whose query
shapes (indexed `store_id, ts_epoch`) are Postgres-portable. For a take-home that
must satisfy `docker compose up` with no manual steps, SQLite removes an entire
service, volume, and failure mode while still demonstrating idempotency, indexing
and graceful degradation (the `_FAIL` hook returns a 503 exactly as a dropped
Postgres connection would). **What would change my mind / first thing that breaks
at 40 live stores:** single-writer contention on the SQLite file. The migration
path is documented — point `db.py` at Postgres and put ingest behind a queue;
nothing above `db.py` changes.

## VLM experiment (staff detection) — prompt and honest verdict

I prototyped a vision-model call on cropped person boxes:

> "You are looking at a cropped image of a single person in a cosmetics retail
> store. Their face is blurred for privacy. Answer strictly JSON:
> {is_staff: bool, confidence: 0-1, cue: '<what you saw>'}. Staff wear a dark
> apron over a branded tee and often stand behind the cash counter. Shoppers
> carry handbags/baskets and browse shelves."

**Verdict: did not ship as default.** It worked on clear crops but added ~300–700 ms
per crop and degraded on occluded/low-res boxes, and the apron cue was
inconsistent under mixed lighting. The rule-based heuristic (behind-counter
polygon + visiting ≥6 zones with >4 min cumulative dwell) matched the five
always-moving salespeople in the POS export at near-zero cost, so the VLM is kept
behind a `--use-vlm` flag for spot-checking rather than the hot path.
