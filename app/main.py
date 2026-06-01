"""FastAPI entrypoint. Run: uvicorn app.main:app --host 0.0.0.0 --port 8000"""
from __future__ import annotations
import json, os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from . import db, metrics as M, funnel as F, anomalies as A, health as H
from .timewin import resolve_window
from .ingestion import ingest_events, IngestBody, MAX_BATCH
from .logging_mw import StructuredLoggingMiddleware

app = FastAPI(title="Store Intelligence API", version="1.0.0")
app.add_middleware(StructuredLoggingMiddleware)

@app.exception_handler(db.DBUnavailable)
async def _down(request: Request, exc: db.DBUnavailable):
    return JSONResponse(status_code=503, content={
        "error": "database_unavailable",
        "message": "Storage backend unreachable; retry shortly.",
        "trace_id": getattr(request.state, "trace_id", None)})

@app.on_event("startup")
def _startup():
    db.init_db()
    db.load_pos_csv()
    seed = os.environ.get("SEED_EVENTS", "/data/sample_events.jsonl")
    try:
        if not db.last_event_epoch_by_store() and os.path.exists(seed):
            with open(seed) as fh:
                ingest_events([json.loads(l) for l in fh if l.strip()])
    except Exception:
        pass

@app.post("/events/ingest")
def ingest(body: IngestBody, request: Request):
    if len(body.events) > MAX_BATCH:
        raise HTTPException(status_code=413,
            detail=f"Batch exceeds {MAX_BATCH} events ({len(body.events)}).")
    request.state.event_count = len(body.events)
    return ingest_events(body.events)

@app.get("/stores/{store_id}/metrics")
def metrics(store_id: str, date: str | None = None):
    s, e, sd, ed = resolve_window(store_id, date)
    return M.compute_metrics(store_id, s, e, sd, ed)

@app.get("/stores/{store_id}/funnel")
def funnel(store_id: str, date: str | None = None):
    s, e, *_ = resolve_window(store_id, date)
    return F.compute_funnel(store_id, s, e)

@app.get("/stores/{store_id}/heatmap")
def heatmap(store_id: str, date: str | None = None):
    s, e, *_ = resolve_window(store_id, date)
    return F.compute_heatmap(store_id, s, e)

@app.get("/stores/{store_id}/anomalies")
def anomalies(store_id: str, date: str | None = None):
    s, e, *_ = resolve_window(store_id, date)
    return A.detect_anomalies(store_id, s, e)

@app.get("/health")
def health():
    return H.health()
