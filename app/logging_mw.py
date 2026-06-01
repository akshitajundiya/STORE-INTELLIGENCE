"""Structured JSON access log: one line per request with trace_id, store_id,
endpoint, latency_ms, event_count (ingest), status_code."""
from __future__ import annotations
import json, logging, sys, time, uuid
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("store_intel")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout); h.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(h); logger.setLevel(logging.INFO)

def _store_id(path):
    p = path.strip("/").split("/")
    return p[1] if len(p) >= 2 and p[0] == "stores" else None

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        tid = request.headers.get("x-trace-id", str(uuid.uuid4()))
        request.state.trace_id = tid
        t0 = time.perf_counter(); status = 500
        try:
            resp = await call_next(request); status = resp.status_code
            resp.headers["x-trace-id"] = tid
            return resp
        finally:
            rec = {"trace_id": tid, "store_id": _store_id(request.url.path),
                   "endpoint": request.url.path, "method": request.method,
                   "latency_ms": round((time.perf_counter()-t0)*1000, 2),
                   "event_count": getattr(request.state, "event_count", None),
                   "status_code": status}
            logger.info(json.dumps({k: v for k, v in rec.items() if v is not None}))
