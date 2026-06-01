"""Event SIMULATOR (NOT the detection pipeline; see pipeline/detect.py for CV).

Generates a labelled event stream consistent with the real POS file so the API
+ dashboard run end-to-end when raw clips aren't mounted (CI, demos, Part E).
Grounded in the actual Brigade Road floor plan + 10-Apr POS timing.

Usage:  LAYOUT_PATH=data/store_layout.json python -m pipeline.simulate > data/sample_events.jsonl
"""
from __future__ import annotations
import csv, json, os, random, sys, uuid
from datetime import datetime, timedelta

random.seed(42)
LAYOUT = json.load(open(os.environ.get("LAYOUT_PATH", "data/store_layout.json")))
POS = os.environ.get("POS_CSV", "data/pos_transactions.csv")
STORE = LAYOUT["store_id"]
BILLING = LAYOUT.get("billing_zone_id", "BILLING")
SHELVES = [z["zone_id"] for z in LAYOUT["zones"]
           if z.get("type") in ("shelf", "engagement", "feature")]

def iso(dt): return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def ev(out, etype, vid, pk, t, cam, zone=None, dwell=0, staff=False, qd=None, seq=None):
    out.append({"event_id": str(uuid.uuid4()), "store_id": STORE, "camera_id": cam,
                "visitor_id": vid, "event_type": etype, "timestamp": iso(t),
                "zone_id": zone, "dwell_ms": dwell, "is_staff": staff,
                "confidence": round(random.uniform(0.61, 0.97), 2),
                "metadata": {"queue_depth": qd, "sku_zone": zone, "session_seq": seq}})

def main():
    rows = list(csv.DictReader(open(POS)))
    out = []

    # Staff (excluded from metrics): 3 uniformed associates roaming all day
    base = datetime(2026, 4, 10, 6, 30, 0)
    for s in range(3):
        for k in range(12):
            t = base + timedelta(minutes=20*k + s*4)
            ev(out, "ZONE_ENTER", f"VIS_staff{s}_{k}", f"STAFF_{s}", t,
               "CAM_FLOOR_01", zone=random.choice(SHELVES + [BILLING]), staff=True)

    # Converting visitors: journey ending at billing just before each POS txn
    persons = []
    for i, r in enumerate(rows, 1):
        tb = datetime.fromisoformat(r["timestamp"].replace("Z", ""))
        vid, pk = f"VIS_{uuid.uuid4().hex[:6]}", f"P{i:03d}"; persons.append((vid, pk, tb))
        t0 = tb - timedelta(minutes=random.randint(8, 18)); seq = 1
        ev(out, "ENTRY", vid, pk, t0, "CAM_ENTRY_01", seq=seq); seq += 1
        t = t0
        for z in random.sample(SHELVES, random.randint(2, 4)):
            t += timedelta(minutes=random.randint(1, 3))
            ev(out, "ZONE_ENTER", vid, pk, t, "CAM_FLOOR_01", zone=z, seq=seq); seq += 1
            ev(out, "ZONE_DWELL", vid, pk, t + timedelta(seconds=30), "CAM_FLOOR_01",
               zone=z, dwell=random.randint(30, 150)*1000, seq=seq); seq += 1
        qd = random.randint(0, 7)
        ev(out, "BILLING_QUEUE_JOIN", vid, pk, tb - timedelta(minutes=2), "CAM_BILLING_01",
           zone=BILLING, qd=qd, seq=seq); seq += 1
        ev(out, "ZONE_ENTER", vid, pk, tb - timedelta(minutes=1), "CAM_BILLING_01",
           zone=BILLING, seq=seq); seq += 1
        ev(out, "EXIT", vid, pk, tb + timedelta(minutes=1), "CAM_ENTRY_01", seq=seq)

    # Non-converting browsers -> conversion < 100%; some abandon the queue
    for j in range(20):
        vid, pk = f"VIS_{uuid.uuid4().hex[:6]}", f"Q{j:03d}"
        t0 = base + timedelta(minutes=random.randint(20, 520))
        ev(out, "ENTRY", vid, pk, t0, "CAM_ENTRY_01", seq=1)
        t = t0
        for z in random.sample(SHELVES, random.randint(1, 3)):
            t += timedelta(minutes=random.randint(1, 4))
            ev(out, "ZONE_ENTER", vid, pk, t, "CAM_FLOOR_01", zone=z)
        if random.random() < 0.4:
            ev(out, "BILLING_QUEUE_JOIN", vid, pk, t + timedelta(minutes=1),
               "CAM_BILLING_01", zone=BILLING, qd=random.randint(3, 9))
            ev(out, "BILLING_QUEUE_ABANDON", vid, pk, t + timedelta(minutes=4),
               "CAM_BILLING_01", zone=BILLING)
        ev(out, "EXIT", vid, pk, t + timedelta(minutes=5), "CAM_ENTRY_01")

    # Re-entry: first buyer leaves & returns -> REENTRY reuses SAME visitor_id (no double count)
    vid0, pk0, tb0 = persons[0]
    ev(out, "REENTRY", vid0, pk0, tb0 + timedelta(minutes=20), "CAM_ENTRY_01", seq=99)

    out.sort(key=lambda e: e["timestamp"])
    for e in out:
        sys.stdout.write(json.dumps(e) + "\n")

if __name__ == "__main__":
    main()
