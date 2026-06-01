"""
app/db.py — SQLite persistence with graceful degradation.

Why SQLite: zero-config, single file, ships inside the container with no extra
service. Schema/access patterns are Postgres-portable (see CHOICES.md §3).

Graceful degradation: db ops raise DBUnavailable; the API maps that to a
structured HTTP 503 with no stack trace (see app/main.py).
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple

DB_PATH = os.environ.get("DB_PATH", "/data/store_intel.db")
POS_CSV = os.environ.get("POS_CSV", "/data/pos_transactions.csv")

_local = threading.local()
_FAIL = {"on": False}  # test hook to simulate DB outage


class DBUnavailable(Exception):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id     TEXT PRIMARY KEY,
    store_id     TEXT NOT NULL,
    camera_id    TEXT NOT NULL,
    visitor_id   TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    ts           TEXT NOT NULL,
    ts_epoch     REAL NOT NULL,
    zone_id      TEXT,
    dwell_ms     INTEGER NOT NULL DEFAULT 0,
    is_staff     INTEGER NOT NULL DEFAULT 0,
    confidence   REAL NOT NULL,
    queue_depth  INTEGER,
    session_seq  INTEGER,
    metadata     TEXT
);
CREATE INDEX IF NOT EXISTS ix_events_store_ts ON events(store_id, ts_epoch);
CREATE INDEX IF NOT EXISTS ix_events_visitor  ON events(store_id, visitor_id);
CREATE INDEX IF NOT EXISTS ix_events_type     ON events(store_id, event_type, ts_epoch);

CREATE TABLE IF NOT EXISTS pos_transactions (
    store_id       TEXT NOT NULL,
    transaction_id TEXT,
    ts             TEXT NOT NULL,
    ts_epoch       REAL NOT NULL,
    basket_value   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_pos_store_ts ON pos_transactions(store_id, ts_epoch);
"""


def _connect() -> sqlite3.Connection:
    if _FAIL["on"]:
        raise DBUnavailable("simulated outage")
    try:
        d = os.path.dirname(DB_PATH)
        if d:
            os.makedirs(d, exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=5.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn
    except sqlite3.Error as e:
        raise DBUnavailable(str(e))


def get_conn() -> sqlite3.Connection:
    if _FAIL["on"]:
        raise DBUnavailable("simulated outage")
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _connect()
        _local.conn = conn
    return conn


@contextmanager
def cursor():
    conn = get_conn()
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        raise DBUnavailable(str(e))
    finally:
        cur.close()


def init_db() -> None:
    with cursor() as cur:
        cur.executescript(SCHEMA)


def healthcheck() -> bool:
    try:
        with cursor() as cur:
            cur.execute("SELECT 1;")
            cur.fetchone()
        return True
    except DBUnavailable:
        return False


def _to_epoch(ts: datetime) -> float:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.timestamp()


def insert_events(events: Iterable) -> Tuple[int, int]:
    """Idempotent bulk insert via INSERT OR IGNORE on PK. Returns (accepted, duplicates)."""
    accepted = duplicates = 0
    with cursor() as cur:
        for ev in events:
            cur.execute(
                """INSERT OR IGNORE INTO events
                   (event_id, store_id, camera_id, visitor_id, event_type, ts, ts_epoch,
                    zone_id, dwell_ms, is_staff, confidence, queue_depth, session_seq, metadata)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    ev.event_id, ev.store_id, ev.camera_id, ev.visitor_id,
                    ev.event_type.value if hasattr(ev.event_type, "value") else ev.event_type,
                    ev.timestamp.isoformat(), _to_epoch(ev.timestamp),
                    ev.zone_id, ev.dwell_ms, int(ev.is_staff), ev.confidence,
                    ev.metadata.queue_depth, ev.metadata.session_seq,
                    json.dumps(ev.metadata.model_dump()),
                ),
            )
            if cur.rowcount == 1:
                accepted += 1
            else:
                duplicates += 1
    return accepted, duplicates


def fetch_events(store_id: str, start_epoch: float, end_epoch: float,
                 include_staff: bool = False) -> List[sqlite3.Row]:
    q = "SELECT * FROM events WHERE store_id=? AND ts_epoch>=? AND ts_epoch<=?"
    params: list = [store_id, start_epoch, end_epoch]
    if not include_staff:
        q += " AND is_staff=0"
    q += " ORDER BY ts_epoch ASC"
    with cursor() as cur:
        cur.execute(q, params)
        return cur.fetchall()


def last_event_epoch_by_store() -> List[Tuple[str, float]]:
    with cursor() as cur:
        cur.execute("SELECT store_id, MAX(ts_epoch) AS last FROM events GROUP BY store_id")
        return [(r["store_id"], r["last"]) for r in cur.fetchall()]


def fetch_pos(store_id: str, start_epoch: float, end_epoch: float) -> List[sqlite3.Row]:
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM pos_transactions WHERE store_id=? AND ts_epoch>=? AND ts_epoch<=? ORDER BY ts_epoch",
            (store_id, start_epoch, end_epoch),
        )
        return cur.fetchall()


def latest_queue_depth(store_id: str, end_epoch: float) -> int:
    with cursor() as cur:
        cur.execute(
            """SELECT queue_depth FROM events
               WHERE store_id=? AND queue_depth IS NOT NULL AND ts_epoch<=?
               ORDER BY ts_epoch DESC LIMIT 1""",
            (store_id, end_epoch),
        )
        row = cur.fetchone()
    return int(row["queue_depth"]) if row and row["queue_depth"] is not None else 0


def load_pos_csv(path: Optional[str] = None) -> int:
    """Load POS. Supports the challenge's simple schema
    (store_id, transaction_id, timestamp, basket_value_inr) AND the real Purplle
    line-item export (order_id, order_date, order_time, total_amount, ...),
    which is rolled up to one row per transaction."""
    import csv as _csv
    from collections import defaultdict

    path = path or POS_CSV
    if not os.path.exists(path):
        return 0

    rows: list[tuple] = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = _csv.DictReader(fh)
        cols = set(reader.fieldnames or [])
        if {"basket_value_inr", "timestamp"} <= cols:
            for r in reader:
                ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
                rows.append((r["store_id"], r.get("transaction_id"),
                             ts.isoformat(), _to_epoch(ts), float(r["basket_value_inr"])))
        else:
            agg: dict = defaultdict(lambda: {"amt": 0.0, "ts": None, "store": None})
            for r in reader:
                oid = r.get("order_id") or r.get("invoice_number")
                d, t = r.get("order_date", ""), r.get("order_time", "00:00:00")
                try:
                    ts = datetime.strptime(f"{d} {t}", "%d-%m-%Y %H:%M:%S")
                except ValueError:
                    continue
                agg[oid]["amt"] += float(r.get("total_amount") or 0)
                agg[oid]["ts"] = ts
                agg[oid]["store"] = r.get("store_id")
            for oid, v in agg.items():
                if v["ts"] is None:
                    continue
                rows.append((v["store"], oid, v["ts"].isoformat(),
                             _to_epoch(v["ts"]), v["amt"]))

    with cursor() as cur:
        cur.execute("DELETE FROM pos_transactions;")
        cur.executemany(
            "INSERT INTO pos_transactions (store_id, transaction_id, ts, ts_epoch, basket_value) VALUES (?,?,?,?,?)",
            rows,
        )
    return len(rows)
