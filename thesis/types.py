"""Shared types for THESIS book and state engines."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class ThesisState(str, Enum):
    HOLDS = "HOLDS"
    WEAKENING = "WEAKENING"
    INVALIDATED = "INVALIDATED"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


@dataclass(frozen=True)
class DepthLevel:
    price: float
    qty: int


@dataclass(frozen=True)
class Ohlc:
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class TickInput:
    """Broker full-mode tick (normalized)."""

    ltp: float
    ohlc: Ohlc
    vtt: int
    tbq: int
    tsq: int
    oi: int
    depth_bid: tuple[DepthLevel, ...]
    depth_ask: tuple[DepthLevel, ...]
    timestamp: float


@dataclass(frozen=True)
class FusionWeights:
    """Book fusion weights (must sum to 100)."""

    volume: int = 30
    oi: int = 30
    absorption: int = 25
    depth: int = 15

    def __post_init__(self) -> None:
        total = self.volume + self.oi + self.absorption + self.depth
        if total != 100:
            raise ValueError(f"fusion weights must sum to 100, got {total}")


# Alias used in spec wording
BookFusionWeights = FusionWeights


@dataclass(frozen=True)
class BookSubScores:
    absorption: int
    liquidity_vacuum: int
    oi_confirmation: int
    volume_follow_through: int


@dataclass(frozen=True)
class BookOutput:
    book_score: int
    divergence_flag: bool
    sweep_risk: bool
    sub_scores: BookSubScores
    price_direction_up: bool


@dataclass(frozen=True)
class ThesisCondition:
    """Boolean condition evaluated against live tick + rolling context."""

    id: str
    label: str
    met: bool
    """If true, condition is part of core structure (entry candle high/low)."""

    is_core: bool = False


@dataclass
class TradeThesis:
    symbol: str
    direction: Direction
    entry_price: float
    stop_loss: float
    target: float
    book_score_baseline: int
    conditions: list[ThesisCondition] = field(default_factory=list)
    dwell_seconds: float = 300.0
    book_drop_weakening_pts: int = 30


@dataclass(frozen=True)
class ThesisOutput:
    state: ThesisState
    reasons: tuple[str, ...]
    decision_line: str
    conditions: tuple[ThesisCondition, ...]
