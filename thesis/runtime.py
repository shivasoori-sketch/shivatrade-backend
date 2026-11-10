"""Process-wide THESIS runtime (Phase 1 in-process)."""

from __future__ import annotations

from thesis.book_engine import BookDivergenceEngine
from thesis.ingestor.feed import FeedIngestor
from thesis.ingestor.redis_store import InMemoryRedisStore, ThesisRedisStore
from thesis.pipeline import ThesisPipeline
from thesis.registry import TradeRegistry
from thesis.thesis_engine import ThesisEngine


class ThesisRuntime:
    _instance: ThesisRuntime | None = None

    def __init__(self) -> None:
        self.redis = InMemoryRedisStore()
        self.store = ThesisRedisStore(self.redis)
        self.registry = TradeRegistry()
        self.pipeline = ThesisPipeline(registry=self.registry)
        self.ingestor = FeedIngestor(
            store=self.store,
            on_tick=self.pipeline.on_tick,
            on_candle_closed=self._on_candle_closed,
        )

    def _on_candle_closed(self, symbol: str, candle) -> None:
        self.pipeline.on_candle_closed(symbol, candle)

    @classmethod
    def get(cls) -> ThesisRuntime:
        if cls._instance is None:
            cls._instance = ThesisRuntime()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None


def get_runtime() -> ThesisRuntime:
    return ThesisRuntime.get()
