"""Ingest HTTP path: forwarder + /ingest/tick."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from main import app
from thesis.runtime import ThesisRuntime


@pytest.fixture(autouse=True)
def _reset_runtime() -> None:
    ThesisRuntime.reset()
    yield
    ThesisRuntime.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_ingest_health(client: TestClient) -> None:
    assert client.get("/ingest/health").json()["ok"] is True


def test_ingest_tick_updates_store(client: TestClient) -> None:
    row = json.loads(
        (Path(__file__).parent / "fixtures/replay/sample_session.jsonl")
        .read_text()
        .splitlines()[0]
    )
    resp = client.post(
        "/ingest/tick",
        json={"symbol": row["symbol"], "raw": row["raw"], "ts": row["ts"]},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    rt = ThesisRuntime.get()
    assert rt.store.latest_tick(row["symbol"]) is not None


def test_ingest_tick_gap_sets_stale(client: TestClient) -> None:
    base = {"ltp": 100.0, "vtt": 1, "tbq": 1, "tsq": 1, "oi": 1}
    client.post("/ingest/tick", json={"symbol": "NSE:X", "raw": base, "ts": 10.0})
    assert client.post("/ingest/tick", json={"symbol": "NSE:X", "raw": base, "ts": 20.0}).json()["data_stale"] is True
    assert client.post("/ingest/tick", json={"symbol": "NSE:X", "raw": base, "ts": 21.0}).json()["data_stale"] is False
