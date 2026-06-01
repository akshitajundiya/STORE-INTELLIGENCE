"""
pipeline/detect.py — Detection + tracking -> structured events.

Each camera is an independent, unsynchronised sensor. We assign a per-camera
visit token to every tracked person and emit what that camera can observe:
  entry   : ENTRY on first appearance (REENTRY if Re-ID matches a recent exit);
            EXIT when the track ends.
  floor   : ZONE_ENTER / ZONE_DWELL (every 30s).
  billing : ZONE_ENTER(BILLING) + BILLING_QUEUE_JOIN from counter occupancy.

Zone assignment: try the calibrated polygon first; if the layout polygons are
uncalibrated (they ship as floor-plan estimates), fall back to lateral position
— each wall camera's shelves are arranged left-to-right, so x maps to the brand
zone. Replace with exact polygons via scripts/calibrate_zones.py for production.
Cross-camera de-dup is a documented limitation (CHOICES.md); the entry camera is
the count-of-record. Confidence is never suppressed.

Run:  python -m pipeline.detect --clips ./clips --layout data/store_layout.json \
        --store STORE_BLR_002 --out data/events.jsonl --fps 15 --stride 3
"""
from __future__ import annotations
import argparse, glob, json, os, time
from datetime import datetime, timedelta, timezone

from pipeline.zones import zone_for_point
from pipeline.tracker import PersonGallery, hist_embedding
from pipeline.staff import StaffHeuristic
from pipeline.emit import make_event, JsonlWriter

DWELL_EMIT_MS = 30_000
_ZS: dict = {}


def _load_layout(path, store_id):
    data = json.load(open(path))
    docs = data if isinstance(data, list) else [data]
    for d in docs:
        if d["store_id"] == store_id:
            return d
    return docs[0]


def _assign_zone(cx, cy, layout, cam_id, cams):
    z = zone_for_point(cx, cy, layout["zones"], cam_id)   # calibrated polygon first
    if z:
        return z
    cam = cams[cam_id]
    role, covers = cam["role"], cam.get("covers", [])
    if role == "billing":
        return "BILLING"
    if role == "floor" and covers:                        # lateral-position fallback
        idx = min(int(max(cx, 0.0) * len(covers)), len(covers) - 1)
        return covers[idx]
    return None


def process(clips_dir, layout_path, store_id, out_path, fps=15, use_vlm=False,
            stride=1, max_frames=0):
    import cv2
    from ultralytics import YOLO
    import supervision as sv

    layout = _load_layout(layout_path, store_id)
    billing_zone = layout.get("billing_zone_id", "BILLING")
    cams = {c["camera_id"]: c for c in layout["cameras"]}
    model = YOLO("yolov8n.pt")
    gallery = PersonGallery()
    staff = StaffHeuristic(billing_zone)
    writer = JsonlWriter(out_path)
    seq: dict[str, int] = {}
    total_events = 0

    def nseq(vid):
        seq[vid] = seq.get(vid, 0) + 1; return seq[vid]

    clip_files = sorted(glob.glob(os.path.join(clips_dir, "*.mp4")))
    if not clip_files:
        print(f"[detect] no .mp4 files found in {clips_dir}"); writer.close(); return
    print(f"[detect] {len(clip_files)} clip(s) found. stride={stride}")

    for cam_file in clip_files:
        cam_id = _match_camera(cam_file, cams)
        if not cam_id:
            print(f"[detect] SKIP (no camera match): {os.path.basename(cam_file)}")
            continue
        role = cams[cam_id]["role"]
        t0 = datetime(2026, 4, 10, 6, 30, tzinfo=timezone.utc)
        tracker = sv.ByteTrack(frame_rate=max(1, fps // stride))
        cap = cv2.VideoCapture(cam_file)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
        print(f"\n[detect] {os.path.basename(cam_file)} -> {cam_id} ({role}), ~{total} frames")
        t_start = time.time(); fno = 0; ev_before = total_events
        seen: dict[int, tuple] = {}
        entry_open: dict[int, tuple] = {}
        q_depth = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if max_frames and fno >= max_frames:
                break
            if fno % stride != 0:
                fno += 1; continue
            ts = t0 + timedelta(seconds=fno / fps)
            H, W = frame.shape[:2]
            res = model(frame, classes=[0], verbose=False)[0]
            dets = sv.Detections.from_ultralytics(res)
            dets = tracker.update_with_detections(dets)
            billing_count = 0
            for xyxy, conf, tid in zip(dets.xyxy, dets.confidence, dets.tracker_id):
                if tid is None:
                    continue
                tid = int(tid)
                x1, y1, x2, y2 = xyxy
                cx, cy = ((x1 + x2) / 2) / W, y2 / H
                crop = frame[int(y1):int(y2), int(x1):int(x2)]
                emb = hist_embedding(crop) if crop.size else None

                if tid not in seen:
                    if role == "entry" and emb is not None:
                        vid, pk, re = gallery.on_entry(tid, emb, ts.timestamp())
                        seen[tid] = (vid, pk)
                        writer.write(make_event(store_id, cam_id, vid,
                            "REENTRY" if re else "ENTRY", ts, confidence=float(conf),
                            session_seq=nseq(vid))); total_events += 1
                        entry_open[tid] = (vid, pk, ts)
                    else:
                        vid = gallery.new_visit_token(); pk = f"P_{cam_id}_{tid}"
                        seen[tid] = (vid, pk)
                vid, pk = seen[tid]
                if role == "entry":
                    entry_open[tid] = (vid, pk, ts)

                if role in ("floor", "billing"):
                    z = _assign_zone(cx, cy, layout, cam_id, cams)
                    if z:
                        key = (vid, z); st = _ZS.get(key)
                        if st is None:
                            _ZS[key] = {"enter": ts, "last": ts}
                            writer.write(make_event(store_id, cam_id, vid, "ZONE_ENTER",
                                ts, zone_id=z, is_staff=staff.is_staff(pk),
                                confidence=float(conf), sku_zone=z, session_seq=nseq(vid)))
                            total_events += 1
                        else:
                            dwell_ms = int((ts - st["enter"]).total_seconds() * 1000)
                            if (ts - st["last"]).total_seconds() * 1000 >= DWELL_EMIT_MS:
                                st["last"] = ts; staff.observe(pk, z, dwell_ms)
                                writer.write(make_event(store_id, cam_id, vid, "ZONE_DWELL",
                                    ts, zone_id=z, dwell_ms=dwell_ms,
                                    is_staff=staff.is_staff(pk), confidence=float(conf),
                                    sku_zone=z, session_seq=nseq(vid))); total_events += 1
                        if z == billing_zone:
                            billing_count += 1
                    if role == "billing" and cy < 0.5:
                        staff.observe(pk, billing_zone, behind_counter=True)

            if role == "billing" and billing_count > q_depth and billing_count > 0:
                for tid, (vid, pk) in seen.items():
                    if not staff.is_staff(pk):
                        writer.write(make_event(store_id, cam_id, vid, "BILLING_QUEUE_JOIN",
                            ts, zone_id=billing_zone, queue_depth=billing_count,
                            session_seq=nseq(vid))); total_events += 1
                        break
            q_depth = billing_count

            if fno % (stride * 150) == 0:
                pct = (100 * fno / total) if total else 0
                rate = fno / (time.time() - t_start + 1e-9)
                print(f"  {os.path.basename(cam_file)}: frame {fno}/{total} "
                      f"({pct:4.1f}%)  {rate:4.1f} fps  events={total_events}", flush=True)
            fno += 1

        for tid, (vid, pk, last_ts) in entry_open.items():
            writer.write(make_event(store_id, cam_id, vid, "EXIT", last_ts,
                confidence=0.5, session_seq=nseq(vid))); total_events += 1
        cap.release()
        print(f"[detect] done {os.path.basename(cam_file)}: "
              f"+{total_events - ev_before} events in {time.time()-t_start:.0f}s")
    writer.close()
    print(f"\n[detect] TOTAL {total_events} events -> {out_path}")


def _match_camera(path, cams):
    name = os.path.basename(path).lower()
    for cid, c in cams.items():
        hint = c.get("file_hint", "").lower().replace(" ", "")
        if hint and hint in name.replace(" ", ""):
            return cid
    for cid, c in cams.items():
        if c["role"] in name:
            return cid
    return None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--clips", required=True)
    ap.add_argument("--layout", default="data/store_layout.json")
    ap.add_argument("--store", default="STORE_BLR_002")
    ap.add_argument("--out", default="data/events.jsonl")
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--max-frames", type=int, default=0)
    ap.add_argument("--use-vlm", action="store_true")
    a = ap.parse_args()
    process(a.clips, a.layout, a.store, a.out, a.fps, a.use_vlm, a.stride, a.max_frames)