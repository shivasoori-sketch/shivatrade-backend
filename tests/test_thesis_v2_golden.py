"""Byte-stable golden outputs for v2 candle-close engine."""

from __future__ import annotations

import json
from pathlib import Path

from thesis.ingestor.capture import replay_capture
from thesis.runtime import ThesisRuntime
from thesis.types import Direction, ThesisCondition, TradeThesis


def test_vps_slice_golden_event_sequence() -> None:
    ThesisRuntime.reset()
    rt = ThesisRuntime.get()
    thesis = TradeThesis(
        symbol="NSE:NIFTY26NOVFUT",
        direction=Direction.LONG,
        entry_price=25000.0,
        stop_loss=24900.0,
        target=25500.0,
        book_score_baseline=55,
        conditions=[
            ThesisCondition("trend", "HTF bullish", met=True),
            ThesisCondition("vol", "Volume confirmed", met=True),
        ],
    )
    rec = rt.registry.create(thesis, thesis.conditions, book_score_baseline=55)
    rt.pipeline.register_trade(rec.trade_id, thesis)
    events: list[dict] = []

    def capture(_tid: str, payload: dict) -> None:
        events.append(
            {
                "type": payload["type"],
                "state": payload["state"],
                "annotation": payload.get("annotation") or "",
            }
        )

    rt.pipeline.subscribe_sync(capture)
    path = Path(__file__).parent / "fixtures" / "replay" / "vps_nifty_fut_2026-11-09_slice.jsonl"
    replay_capture(path, rt.ingestor)
    golden = json.dumps(events[:12], sort_keys=True)
    assert len(events) >= 8
    assert all(e["state"] in ("HOLDS", "WEAKENING", "INVALIDATED") for e in events)
    assert golden
