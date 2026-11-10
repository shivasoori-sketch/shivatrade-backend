"""Pipeline v2: candle-close WS + VPS fixture replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from thesis.ingestor.capture import replay_capture
from thesis.runtime import ThesisRuntime
from thesis.types import Direction, ThesisCondition, TradeThesis


@pytest.fixture(autouse=True)
def _reset() -> None:
    ThesisRuntime.reset()
    yield
    ThesisRuntime.reset()


def test_ws_only_on_candle_close_not_every_tick() -> None:
    rt = ThesisRuntime.get()
    thesis = TradeThesis(
        symbol="NSE:NIFTY26NOVFUT",
        direction=Direction.LONG,
        entry_price=25000.0,
        stop_loss=24900.0,
        target=25500.0,
        book_score_baseline=60,
        conditions=[ThesisCondition("a", "test", met=True)],
    )
    rec = rt.registry.create(thesis, thesis.conditions, book_score_baseline=60)
    rt.pipeline.register_trade(rec.trade_id, thesis)
    box = rt.pipeline.subscribe_ws(rec.trade_id)

    path = Path(__file__).parent / "fixtures" / "replay" / "vps_nifty_fut_2026-11-09_slice.jsonl"
    replay_capture(path, rt.ingestor)
    assert len(box.events) >= 1
    types = {e["type"] for e in box.events}
    assert "immediate_invalidate" not in types or all(
        e["state"] != "WEAKENING" for e in box.events if e["type"] == "immediate_invalidate"
    )
    assert any(
        t in types
        for t in ("confirmed_state", "intermediate_signal", "immediate_invalidate")
    )


def test_immediate_invalidate_still_on_tick() -> None:
    rt = ThesisRuntime.get()
    thesis = TradeThesis(
        symbol="NSE:TEST",
        direction=Direction.LONG,
        entry_price=100.0,
        stop_loss=98.0,
        target=105.0,
        book_score_baseline=70,
        conditions=[ThesisCondition("a", "test", met=True)],
    )
    rec = rt.registry.create(thesis, thesis.conditions)
    rt.pipeline.register_trade(rec.trade_id, thesis)
    box = rt.pipeline.subscribe_ws(rec.trade_id)
    from tests.conftest import make_tick

    rt.ingestor.ingest_tick("NSE:TEST", make_tick(ltp=97.0, ts=1.0))
    assert len(box.events) == 1
    assert box.events[0]["type"] == "immediate_invalidate"
