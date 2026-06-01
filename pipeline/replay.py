"""Stream events.jsonl to the API at simulated real time (Part E).
Proves the pipeline and API are genuinely connected, not batch-loaded.

Run:  python -m pipeline.replay --events data/sample_events.jsonl \
        --api http://localhost:8000 --speed 60
"""
from __future__ import annotations
import argparse, json, time
from datetime import datetime
import urllib.request

def post(api, batch):
    req = urllib.request.Request(f"{api}/events/ingest",
        data=json.dumps({"events": batch}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", default="data/sample_events.jsonl")
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--speed", type=float, default=60.0, help="x real-time")
    ap.add_argument("--batch", type=int, default=10)
    a = ap.parse_args()

    evs = [json.loads(l) for l in open(a.events) if l.strip()]
    evs.sort(key=lambda e: e["timestamp"])
    t_prev = None; buf = []
    for e in evs:
        t = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
        if t_prev is not None:
            gap = (t - t_prev).total_seconds() / a.speed
            if gap > 0:
                if buf:
                    print("ingest", post(a.api, buf)); buf = []
                time.sleep(min(gap, 2.0))
        buf.append(e); t_prev = t
        if len(buf) >= a.batch:
            print("ingest", post(a.api, buf)); buf = []
    if buf:
        print("ingest", post(a.api, buf))

if __name__ == "__main__":
    main()
