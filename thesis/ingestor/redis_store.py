"""Redis layout for ticks, rolling windows, and data_stale."""

from __future__ import annotations

import json
from typing import Protocol

from thesis.ingestor import keys
from thesis.types import DepthLevel, Ohlc, TickInput


def _tick_to_hash(tick: TickInput) -> dict[str, str]:
    return {
        "ltp": str(tick.ltp),
        "open": str(tick.ohlc.open),
        "high": str(tick.ohlc.high),
        "low": str(tick.ohlc.low),
        "close": str(tick.ohlc.close),
        "vtt": str(tick.vtt),
        "tbq": str(tick.tbq),
        "tsq": str(tick.tsq),
        "oi": str(tick.oi),
        "timestamp": str(tick.timestamp),
        "depth_bid": json.dumps(
            [{"price": d.price, "qty": d.qty} for d in tick.depth_bid]
        ),
        "depth_ask": json.dumps(
            [{"price": d.price, "qty": d.qty} for d in tick.depth_ask]
        ),
    }


def tick_from_hash(data: dict[str, str]) -> TickInput | None:
    if not data or "ltp" not in data:
        return None
    bid = tuple(
        DepthLevel(price=float(x["price"]), qty=int(x["qty"]))
        for x in json.loads(data.get("depth_bid") or "[]")
    )
    ask = tuple(
        DepthLevel(price=float(x["price"]), qty=int(x["qty"]))
        for x in json.loads(data.get("depth_ask") or "[]")
    )
    return TickInput(
        ltp=float(data["ltp"]),
        ohlc=Ohlc(
            open=float(data["open"]),
            high=float(data["high"]),
            low=float(data["low"]),
            close=float(data["close"]),
        ),
        vtt=int(data["vtt"]),
        tbq=int(data["tbq"]),
        tsq=int(data["tsq"]),
        oi=int(data["oi"]),
        depth_bid=bid,
        depth_ask=ask,
        timestamp=float(data["timestamp"]),
    )


class RedisLike(Protocol):
    def hset(self, name: str, mapping: dict[str, str]) -> None: ...
    def hgetall(self, name: str) -> dict[str, str]: ...
    def rpush(self, name: str, value: str) -> None: ...
    def ltrim(self, name: str, start: int, end: int) -> None: ...
    def lrange(self, name: str, start: int, end: int) -> list[str]: ...
    def set(self, name: str, value: str) -> None: ...
    def get(self, name: str) -> str | None: ...


class InMemoryRedisStore:
    """Test/dev backend implementing spec key layout."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}
        self._strings: dict[str, str] = {}

    def hset(self, name: str, mapping: dict[str, str]) -> None:
        self._hashes.setdefault(name, {}).update(mapping)

    def hgetall(self, name: str) -> dict[str, str]:
        return dict(self._hashes.get(name, {}))

    def rpush(self, name: str, value: str) -> None:
        self._lists.setdefault(name, []).append(value)
        self.ltrim(name, -keys.WINDOW_CAP, -1)

    def ltrim(self, name: str, start: int, end: int) -> None:
        lst = self._lists.get(name, [])
        if not lst:
            return
        n = len(lst)
        if start < 0:
            start = max(0, n + start)
        if end < 0:
            end = n + end
        self._lists[name] = lst[start : end + 1]

    def lrange(self, name: str, start: int, end: int) -> list[str]:
        lst = self._lists.get(name, [])
        if end == -1:
            end = len(lst) - 1
        return lst[start : end + 1]

    def set(self, name: str, value: str) -> None:
        self._strings[name] = value

    def get(self, name: str) -> str | None:
        return self._strings.get(name)


class ThesisRedisStore:
    def __init__(self, redis: RedisLike) -> None:
        self.redis = redis

    def write_tick(self, symbol: str, tick: TickInput) -> None:
        self.redis.hset(keys.tick_hash(symbol), _tick_to_hash(tick))
        self.redis.rpush(keys.win_ltp(symbol), str(tick.ltp))
        self.redis.rpush(keys.win_vtt(symbol), str(tick.vtt))
        self.redis.rpush(keys.win_oi(symbol), str(tick.oi))
        depth_qty = sum(d.qty for d in tick.depth_bid) + sum(d.qty for d in tick.depth_ask)
        prev_d = self.redis.get(keys.baseline_depth(symbol))
        prev_v = self.redis.get(keys.baseline_vol(symbol))
        base_d = float(prev_d) if prev_d else float(depth_qty)
        base_v = float(prev_v) if prev_v else float(tick.vtt)
        if prev_d:
            base_d = 0.95 * base_d + 0.05 * depth_qty
        if prev_v:
            base_v = 0.9 * base_v + 0.1 * tick.vtt
        self.redis.set(keys.baseline_depth(symbol), str(base_d))
        self.redis.set(keys.baseline_vol(symbol), str(base_v))

    def latest_tick(self, symbol: str) -> TickInput | None:
        return tick_from_hash(self.redis.hgetall(keys.tick_hash(symbol)))

    def set_data_stale(self, symbol: str, stale: bool) -> None:
        self.redis.set(keys.data_stale_key(symbol), "1" if stale else "0")

    def is_data_stale(self, symbol: str) -> bool:
        return self.redis.get(keys.data_stale_key(symbol)) == "1"
