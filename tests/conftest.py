import os, tempfile, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
# Env MUST be set before importing app (layout/db read it at import time).
os.environ["LAYOUT_PATH"] = str(ROOT / "data" / "store_layout.json")
os.environ["POS_CSV"]     = str(ROOT / "data" / "pos_transactions.csv")
os.environ["SEED_EVENTS"] = str(ROOT / "data" / "sample_events.jsonl")
os.environ["DB_PATH"]     = os.path.join(tempfile.mkdtemp(), "test.db")

import json, pytest
from fastapi.testclient import TestClient
from app.main import app
from app import db

@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:      # startup seeds the sample events
        yield c

@pytest.fixture(autouse=True)
def _reset_fail():
    db._FAIL["on"] = False
    yield
    db._FAIL["on"] = False

def seed_events():
    return [json.loads(l) for l in open(os.environ["SEED_EVENTS"]) if l.strip()]
