"""FastAPI THESIS routes."""

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


def _seed_ticks(symbol: str = "NSE:TEST") -> None:
    rt = ThesisRuntime.get()
    path = Path(__file__).parent / "fixtures" / "replay" / "sample_session.jsonl"
    from thesis.ingestor import MockBrokerAdapter

    ticks = []
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if row["symbol"] == symbol:
            ticks.append((row["symbol"], row["raw"], float(row["ts"])))
    MockBrokerAdapter(rt.ingestor, ticks).run()


def test_create_and_poll_state(client: TestClient) -> None:
    _seed_ticks()
    resp = client.post(
        "/trade",
        json={
            "symbol": "NSE:TEST",
            "direction": "long",
            "entry_price": 100.0,
            "stop_loss": 98.0,
            "target": 105.0,
            "conditions": [
                {"id": "htf", "label": "HTF trend bullish", "met": True},
                {"id": "vwap", "label": "Above VWAP", "met": True},
            ],
        },
    )
    assert resp.status_code == 200
    trade_id = resp.json()["trade_id"]
    assert resp.json()["book_score_baseline"] > 0

    state = client.get(f"/trade/{trade_id}/state").json()
    assert state["state"] in ("HOLDS", "WEAKENING", "INVALIDATED")
    assert "data_stale" in state

    book = client.get(f"/trade/{trade_id}/book")
    assert book.status_code == 200
    assert 0 <= book.json()["book_score"] <= 100


def test_exit_and_journal(client: TestClient) -> None:
    _seed_ticks()
    trade_id = client.post(
        "/trade",
        json={
            "symbol": "NSE:TEST",
            "direction": "long",
            "entry_price": 100.0,
            "stop_loss": 98.0,
            "target": 105.0,
            "conditions": [{"id": "a", "label": "test", "met": True}],
        },
    ).json()["trade_id"]
    ex = client.post(
        f"/trade/{trade_id}/exit",
        json={"held_to_plan": True, "exit_reason": "target", "outcome_r": 1.5},
    )
    assert ex.json()["status"] == "exited"
    journal = client.get("/journal").json()
    assert any(r["trade_id"] == trade_id for r in journal["trades"])


def test_ws_emits_only_on_state_change(client: TestClient) -> None:
    rt = ThesisRuntime.get()
    trade_id = client.post(
        "/trade",
        json={
            "symbol": "NSE:TEST",
            "direction": "long",
            "entry_price": 100.0,
            "stop_loss": 98.0,
            "target": 105.0,
            "book_score_baseline": 80,
            "conditions": [
                {"id": "htf", "label": "HTF", "met": True},
                {"id": "vwap", "label": "VWAP", "met": True},
            ],
        },
    ).json()["trade_id"]

    from tests.conftest import make_tick

    mailbox = rt.pipeline.subscribe_ws(trade_id)
    tick = make_tick(ltp=97.5, ts=5000.0)
    rt.ingestor.ingest_tick("NSE:TEST", tick)
    assert len(mailbox.events) == 1
    assert mailbox.events[0]["state"] == "INVALIDATED"

    with client.websocket_connect(f"/trade/{trade_id}/stream"):
        pass


def test_get_trade_summary(client: TestClient) -> None:
    trade_id = client.post(
        "/trade",
        json={
            "symbol": "NSE:TEST",
            "direction": "long",
            "entry_price": 100.0,
            "stop_loss": 98.0,
            "target": 105.0,
            "conditions": [{"id": "a", "label": "test", "met": True}],
        },
    ).json()["trade_id"]
    summary = client.get(f"/trade/{trade_id}")
    assert summary.status_code == 200
    body = summary.json()
    assert body["trade_id"] == trade_id
    assert body["entry_price"] == 100.0
    assert body["status"] == "active"
