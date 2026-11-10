"""Ingestor + Redis layout + replay fixture tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from thesis.ingestor import FeedIngestor, InMemoryRedisStore, MockBrokerAdapter, ThesisRedisStore
from thesis.ingestor import keys
from thesis.runtime import ThesisRuntime


@pytest.fixture(autouse=True)
def _reset_runtime() -> None:
    ThesisRuntime.reset()
    yield
    ThesisRuntime.reset()


def test_redis_keys_after_tick() -> None:
    redis = InMemoryRedisStore()
    store = ThesisRedisStore(redis)
    ingestor = FeedIngestor(store=store)
    raw = {
        "ltp": 2500.0,
        "vtt": 900,
        "tbq": 100,
        "tsq": 120,
        "oi": 50000,
        "depth": {"buy": [{"price": 2499.5, "quantity": 100}], "sell": [{"price": 2500.5, "quantity": 90}]},
    }
    ingestor.on_raw_tick("NSE:INFY", raw, timestamp=1.0)
    assert redis.hgetall(keys.tick_hash("NSE:INFY"))["ltp"] == "2500.0"
    assert len(redis.lrange(keys.win_ltp("NSE:INFY"), 0, -1)) == 1
    assert redis.get(keys.baseline_depth("NSE:INFY")) is not None


def test_data_stale_on_gap() -> None:
    redis = InMemoryRedisStore()
    store = ThesisRedisStore(redis)
    ingestor = FeedIngestor(store=store, gap_threshold_seconds=5.0)
    base = {"ltp": 100.0, "vtt": 1, "tbq": 1, "tsq": 1, "oi": 1}
    ingestor.on_raw_tick("NSE:X", base, timestamp=10.0)
    assert store.is_data_stale("NSE:X") is False
    ingestor.on_raw_tick("NSE:X", base, timestamp=20.0)
    assert store.is_data_stale("NSE:X") is True
    ingestor.on_raw_tick("NSE:X", base, timestamp=21.0)
    assert store.is_data_stale("NSE:X") is False


def test_replay_jsonl_fixture() -> None:
    rt = ThesisRuntime.get()
    path = Path(__file__).parent / "fixtures" / "replay" / "sample_session.jsonl"
    ticks: list[tuple[str, dict, float]] = []
    for line in path.read_text().splitlines():
        row = json.loads(line)
        ticks.append((row["symbol"], row["raw"], float(row["ts"])))
    MockBrokerAdapter(rt.ingestor, ticks).run()
    latest = rt.store.latest_tick("NSE:TEST")
    assert latest is not None
    assert latest.ltp == 100.2
    assert len(rt.redis.lrange(keys.win_ltp("NSE:TEST"), 0, -1)) == 5


def test_reconnect_backoff_increases() -> None:
    redis = InMemoryRedisStore()
    ingestor = FeedIngestor(store=ThesisRedisStore(redis))
    assert ingestor.connected is True
    ingestor.mark_disconnected()
    assert ingestor.connected is False
    b1 = ingestor.reconnect_backoff_seconds()
    ingestor.mark_disconnected()
    b2 = ingestor.reconnect_backoff_seconds()
    assert b2 >= b1
