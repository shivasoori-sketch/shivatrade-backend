"""Build 1-minute OHLCV candles from LTP + LTQ (Zerodha path; authoritative over broker OHLC)."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from thesis.ingestor import keys  # package __init__ is lightweight (no feed import)
from thesis.ingestor.redis_store import RedisLike, ThesisRedisStore
from thesis.types import Ohlc, TickInput

CandleClosedHandler = Callable[[str, "ClosedCandle1m"], None]


def minute_start_epoch(ts: float) -> int:
    return int(ts // 60) * 60


@dataclass(frozen=True)
class BuildingCandle1m:
    minute_start: int
    open: float
    high: float
    low: float
    close: float
    volume: int

    @classmethod
    def from_tick(cls, tick: TickInput) -> BuildingCandle1m:
        m = minute_start_epoch(tick.timestamp)
        return cls(
            minute_start=m,
            open=tick.ltp,
            high=tick.ltp,
            low=tick.ltp,
            close=tick.ltp,
            volume=max(0, tick.ltq),
        )

    def merge_tick(self, tick: TickInput) -> BuildingCandle1m:
        vol = self.volume + max(0, tick.ltq)
        return BuildingCandle1m(
            minute_start=self.minute_start,
            open=self.open,
            high=max(self.high, tick.ltp),
            low=min(self.low, tick.ltp),
            close=tick.ltp,
            volume=vol,
        )


@dataclass(frozen=True)
class ClosedCandle1m:
    minute_start: int
    ohlc: Ohlc
    volume: int

    def to_json(self) -> str:
        return json.dumps(
            {
                "minute_start": self.minute_start,
                "open": self.ohlc.open,
                "high": self.ohlc.high,
                "low": self.ohlc.low,
                "close": self.ohlc.close,
                "volume": self.volume,
            }
        )

    @classmethod
    def from_building(cls, candle: BuildingCandle1m) -> ClosedCandle1m:
        return cls(
            minute_start=candle.minute_start,
            ohlc=Ohlc(
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
            ),
            volume=candle.volume,
        )

    @classmethod
    def from_json(cls, raw: str) -> ClosedCandle1m:
        data = json.loads(raw)
        return cls(
            minute_start=int(data["minute_start"]),
            ohlc=Ohlc(
                open=float(data["open"]),
                high=float(data["high"]),
                low=float(data["low"]),
                close=float(data["close"]),
            ),
            volume=int(data["volume"]),
        )


def _candle_hash(candle: BuildingCandle1m) -> dict[str, str]:
    return {
        "minute_start": str(candle.minute_start),
        "open": str(candle.open),
        "high": str(candle.high),
        "low": str(candle.low),
        "close": str(candle.close),
        "volume": str(candle.volume),
    }


def building_from_hash(data: dict[str, str]) -> BuildingCandle1m | None:
    if not data or "open" not in data:
        return None
    return BuildingCandle1m(
        minute_start=int(data.get("minute_start") or 0),
        open=float(data["open"]),
        high=float(data["high"]),
        low=float(data["low"]),
        close=float(data["close"]),
        volume=int(data.get("volume") or 0),
    )


class CandleBuilder:
    """Accumulate ticks into the current 1m candle; close on minute boundary."""

    def __init__(
        self,
        store: ThesisRedisStore,
        *,
        on_candle_closed: CandleClosedHandler | None = None,
    ) -> None:
        self.store = store
        self.on_candle_closed = on_candle_closed
        self._local: dict[str, BuildingCandle1m] = {}

    @property
    def redis(self) -> RedisLike:
        return self.store.redis

    def on_tick(self, symbol: str, tick: TickInput) -> ClosedCandle1m | None:
        tick_minute = minute_start_epoch(tick.timestamp)
        current = self._local.get(symbol)
        if current is None:
            loaded = building_from_hash(
                self.redis.hgetall(keys.candle_1m_current(symbol))
            )
            if loaded and loaded.minute_start == tick_minute:
                current = loaded
            elif loaded and loaded.minute_start < tick_minute:
                closed = self._close(symbol, current=loaded)
                current = None
            else:
                current = None

        closed: ClosedCandle1m | None = None
        if current is not None and tick_minute > current.minute_start:
            closed = self._close(symbol, current=current)
            current = None

        if current is None:
            current = BuildingCandle1m.from_tick(tick)
        else:
            current = current.merge_tick(tick)

        self._local[symbol] = current
        self.redis.hset(keys.candle_1m_current(symbol), _candle_hash(current))
        return closed

    def _close(
        self, symbol: str, *, current: BuildingCandle1m
    ) -> ClosedCandle1m:
        closed = ClosedCandle1m.from_building(current)
        self.redis.rpush(keys.candle_1m_closed(symbol), closed.to_json())
        self.redis.ltrim(
            keys.candle_1m_closed(symbol),
            -keys.CLOSED_CANDLE_CAP,
            -1,
        )
        self.redis.delete(keys.candle_1m_current(symbol))
        self._local.pop(symbol, None)
        if self.on_candle_closed:
            self.on_candle_closed(symbol, closed)
        return closed

    def current(self, symbol: str) -> BuildingCandle1m | None:
        if symbol in self._local:
            return self._local[symbol]
        return building_from_hash(self.redis.hgetall(keys.candle_1m_current(symbol)))

    def last_closed(self, symbol: str) -> list[ClosedCandle1m]:
        raw = self.redis.lrange(keys.candle_1m_closed(symbol), 0, -1)
        return [ClosedCandle1m.from_json(line) for line in raw]
