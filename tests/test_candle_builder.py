"""1m candle builder from LTP + LTQ (THESIS v2 Phase 0)."""

from __future__ import annotations

from thesis.candle_builder import CandleBuilder, minute_start_epoch
from thesis.ingestor import keys
from thesis.ingestor.feed import FeedIngestor
from thesis.ingestor.redis_store import InMemoryRedisStore, ThesisRedisStore
from thesis.types import Ohlc, TickInput


def _tick(ltp: float, ts: float, ltq: int = 1) -> TickInput:
    return TickInput(
        ltp=ltp,
        ohlc=Ohlc(open=ltp, high=ltp, low=ltp, close=ltp),
        ltq=ltq,
        vtt=1000,
        tbq=1,
        tsq=1,
        oi=1,
        depth_bid=(),
        depth_ask=(),
        timestamp=ts,
    )


def test_single_minute_builds_current_candle() -> None:
    redis = InMemoryRedisStore()
    store = ThesisRedisStore(redis)
    builder = CandleBuilder(store)
    base = 1_700_000_000.0
    builder.on_tick("NSE:SBIN", _tick(500.0, base + 10, ltq=5))
    builder.on_tick("NSE:SBIN", _tick(502.0, base + 30, ltq=3))
    cur = builder.current("NSE:SBIN")
    assert cur is not None
    assert cur.open == 500.0
    assert cur.high == 502.0
    assert cur.low == 500.0
    assert cur.close == 502.0
    assert cur.volume == 8
    assert minute_start_epoch(base + 10) == cur.minute_start
    h = redis.hgetall(keys.candle_1m_current("NSE:SBIN"))
    assert h["close"] == "502.0"


def test_minute_boundary_closes_and_keeps_last_three() -> None:
    redis = InMemoryRedisStore()
    store = ThesisRedisStore(redis)
    builder = CandleBuilder(store)
    m0 = 1_700_000_100.0
    m1 = m0 + 60.0
    m2 = m0 + 120.0
    builder.on_tick("NSE:X", _tick(10.0, m0 + 5, ltq=2))
    builder.on_tick("NSE:X", _tick(12.0, m0 + 50, ltq=4))
    c1 = builder.on_tick("NSE:X", _tick(11.0, m1 + 1, ltq=1))
    assert c1 is not None
    assert c1.ohlc.open == 10.0
    assert c1.ohlc.close == 12.0
    assert c1.volume == 6

    builder.on_tick("NSE:X", _tick(13.0, m2 + 1, ltq=2))
    closed = builder.last_closed("NSE:X")
    assert len(closed) == 2

    for i in range(5):
        t = m2 + 60 * (i + 1) + 1
        builder.on_tick("NSE:X", _tick(10.0 + i, t, ltq=1))
    assert len(builder.last_closed("NSE:X")) <= 3


def test_ingestor_wires_candle_keys() -> None:
    redis = InMemoryRedisStore()
    store = ThesisRedisStore(redis)
    ingestor = FeedIngestor(store=store, build_candles=True)
    raw = {"ltp": 100.0, "ltq": 7, "vtt": 1, "tbq": 1, "tsq": 1, "oi": 1}
    ingestor.on_raw_tick("NSE:Y", raw, timestamp=1_700_000_000.0)
    assert redis.hgetall(keys.candle_1m_current("NSE:Y"))["volume"] == "7"
