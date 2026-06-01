#!/usr/bin/env bash
# One command: process all CCTV clips in ./clips -> data/events.jsonl
set -euo pipefail
CLIPS="${1:-./clips}"
STORE="${2:-STORE_BLR_002}"
python -m pipeline.detect --clips "$CLIPS" --layout data/store_layout.json \
  --store "$STORE" --out data/events.jsonl --fps 15
echo "Done. Feed into the API with:"
echo "  python -m pipeline.replay --events data/events.jsonl --api http://localhost:8000 --speed 60"
