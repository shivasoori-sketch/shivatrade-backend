"""Feed ingestor with gap detection, data_stale, and reconnect hooks."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from thesis.ingestor.normalize import normalize_broker_tick
from thesis.ingestor.redis_store import ThesisRedisStore
from thesis.types import TickInput


TickHandler = Callable[[str, TickInput], None]


@dataclass
class FeedIngestor:
    store: ThesisRedisStore
    gap_threshold_seconds: float = 5.0
    on_tick: TickHandler | None = None
    _last_ts: dict[str, float] = field(default_factory=dict)
    _reconnect_attempts: int = 0
    _connected: bool = True

    def ingest_tick(self, symbol: str, tick: TickInput) -> None:
        last = self._last_ts.get(symbol)
        if last is not None and tick.timestamp - last > self.gap_threshold_seconds:
            self.store.set_data_stale(symbol, True)
        elif self.store.is_data_stale(symbol) and last is not None:
            if tick.timestamp - last <= self.gap_threshold_seconds:
                self.store.set_data_stale(symbol, False)

        self.store.write_tick(symbol, tick)
        self._last_ts[symbol] = tick.timestamp
        if self.on_tick:
            self.on_tick(symbol, tick)

    def on_raw_tick(
        self, symbol: str, raw: dict, *, timestamp: float | None = None
    ) -> TickInput:
        tick = normalize_broker_tick(raw, symbol=symbol, timestamp=timestamp)
        if tick.timestamp <= 0:
            tick = replace(tick, timestamp=time.time())
        self.ingest_tick(symbol, tick)
        return tick

    def mark_disconnected(self) -> None:
        self._connected = False
        self._reconnect_attempts += 1

    def mark_connected(self) -> None:
        self._connected = True

    @property
    def connected(self) -> bool:
        return self._connected

    def reconnect_backoff_seconds(self) -> float:
        return min(60.0, 2.0**min(self._reconnect_attempts, 5))


@dataclass
class MockBrokerAdapter:
    """Replay raw broker dicts into the ingestor (tests / local)."""

    ingestor: FeedIngestor
    ticks: list[tuple[str, dict, float | None]]

    def run(self) -> list[TickInput]:
        out: list[TickInput] = []
        for symbol, raw, ts in self.ticks:
            out.append(self.ingestor.on_raw_tick(symbol, raw, timestamp=ts))
        return out
