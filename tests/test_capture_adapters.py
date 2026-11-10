"""Phase 0 capture mode and broker adapter stubs."""

from __future__ import annotations

import json
from pathlib import Path

from thesis.ingestor import FeedIngestor, InMemoryRedisStore, ThesisRedisStore
from thesis.ingestor.adapters import adapt_upstox_tick, adapt_zerodha_tick
from thesis.ingestor.capture import CaptureSession


def test_capture_jsonl_roundtrip(tmp_path: Path) -> None:
    out = tmp_path / "session.jsonl"
    redis = InMemoryRedisStore()
    ingestor = FeedIngestor(
        store=ThesisRedisStore(redis),
        build_candles=False,
        capture_session=CaptureSession(out, "zerodha").open(),
    )
    raw = {"last_price": 2500, "last_traded_quantity": 15, "volume_traded": 9}
    ingestor.on_raw_tick("NSE:INFY", raw, timestamp=100.0)
    ingestor.capture_session.close()
    rows = CaptureSession.load_records(out)
    assert len(rows) == 1
    assert rows[0]["broker"] == "zerodha"
    assert rows[0]["mode"] == "full"
    assert json.loads(json.dumps(rows[0]["raw"])) == raw


def test_adapt_upstox_schema() -> None:
    msg = {
        "ltpc": {"ltp": 100.5, "ltq": 25},
        "marketLevel": {"bid": [{"price": 100.0, "quantity": 10}], "ask": []},
        "vtt": 5000,
        "oi": 12000,
        "tbq": 1,
        "tsq": 2,
        "timestamp": 99.0,
    }
    adapted = adapt_upstox_tick(msg, symbol="NSE:SBIN")
    assert adapted["ltp"] == 100.5
    assert adapted["ltq"] == 25
    assert adapted["_source"] == "upstox_full"


def test_adapt_zerodha_marks_prior_day_ohlc() -> None:
    tick = {
        "last_price": 50.0,
        "last_traded_quantity": 3,
        "volume_traded": 100,
        "ohlc": {"open": 1, "high": 2, "low": 0.5, "close": 1.5},
        "exchange_timestamp": 50.0,
    }
    adapted = adapt_zerodha_tick(tick, symbol="NSE:RELIANCE")
    assert adapted["_ohlc_is_prior_day"] is True
    assert adapted["ltq"] == 3
