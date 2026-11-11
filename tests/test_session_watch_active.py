"""GET /trade/active — default session watch for public kaaldrishti."""

from __future__ import annotations

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


def test_active_creates_session_watch(client: TestClient) -> None:
    first = client.get("/trade/active")
    assert first.status_code == 200
    body = first.json()
    assert body["mode"] == "session_watch"
    assert body["trade_id"]
    assert body["status"] == "active"
    assert "validation" in body["session_message"].lower()

    second = client.get("/trade/active")
    assert second.json()["trade_id"] == body["trade_id"]

    state = client.get(f"/trade/{body['trade_id']}/state").json()
    assert state["mode"] == "session_watch"
    assert state["depth"] is not None
    assert state["state"] in ("HOLDS", "WEAKENING", "INVALIDATED")
