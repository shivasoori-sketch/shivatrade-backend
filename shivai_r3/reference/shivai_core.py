"""SHIVAI R3 research-only deterministic reference kernel.

No broker, network, orders, credential loading or live deployment code.
This is a deliberately small baseline for fixture review, NOT a production signal engine.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional


class Quality(str, Enum):
    LIVE_VERIFIED = "LIVE_VERIFIED"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


class EpisodeState(str, Enum):
    WATCH = "WATCH"
    ATTEMPT = "ATTEMPT"
    ACCEPTANCE_PENDING = "ACCEPTANCE_PENDING"
    BREAKOUT_CONFIRMED_RESEARCH = "BREAKOUT_CONFIRMED_RESEARCH"
    FAILED_ACCEPTANCE = "FAILED_ACCEPTANCE"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class Bar:
    instrument: str
    timeframe_s: int
    end_ms: int
    close: Decimal
    finalized_known_ms: int
    complete: bool = True
    degraded: bool = False


@dataclass(frozen=True)
class Zone:
    zone_id: str
    version: int
    instrument: str
    boundary: Decimal
    side: str  # RESISTANCE or SUPPORT
    confirmed_known_ms: int


@dataclass(frozen=True)
class OptionQuote:
    contract: str
    bid: Decimal
    ask: Decimal
    known_ms: int
    expiry_ms: int
    size_at_bid: int = 0
    size_at_ask: int = 0


@dataclass(frozen=True)
class VirtualTrade:
    trade_id: str
    contract: str
    entry_ask: Decimal
    entry_known_ms: int
    stop_bid: Decimal
    target_bid: Decimal
    status: str = "OPEN"
    exit_bid: Optional[Decimal] = None
    exit_known_ms: Optional[int] = None

    def evaluate(self, q: OptionQuote) -> VirtualTrade:
        from dataclasses import replace
        if self.status != "OPEN" or q.contract != self.contract or q.known_ms <= self.entry_known_ms:
            return self
        if q.bid <= self.stop_bid:
            return replace(self, status="STOP", exit_bid=q.bid, exit_known_ms=q.known_ms)
        if q.bid >= self.target_bid:
            return replace(self, status="TARGET", exit_bid=q.bid, exit_known_ms=q.known_ms)
        return self


@dataclass
class BreakoutEpisode:
    zone: Zone
    atr_prior_15m: Decimal
    state: EpisodeState = EpisodeState.WATCH
    qualifying_end_ms: Optional[int] = None
    confirmation_count: int = 0
    known_ms: Optional[int] = None
    reason: Optional[str] = None
    history: list[tuple[str, int, str]] = field(default_factory=list)

    def _transition(self, state: EpisodeState, known_ms: int, reason: str) -> None:
        if self.known_ms is not None and known_ms < self.known_ms:
            raise ValueError("Knowledge time cannot move backward")
        self.state, self.known_ms, self.reason = state, known_ms, reason
        self.history.append((state.value, known_ms, reason))

    def observed_cross(self, price: Decimal, known_ms: int, quality: Quality) -> None:
        if quality != Quality.LIVE_VERIFIED or self.state != EpisodeState.WATCH:
            return
        if known_ms < self.zone.confirmed_known_ms:
            return
        crossed = price > self.zone.boundary if self.zone.side == "RESISTANCE" else price < self.zone.boundary
        if crossed:
            self._transition(EpisodeState.ATTEMPT, known_ms, "CROSSED_BOUNDARY")

    def completed_3m(self, bar: Bar) -> None:
        if self.state != EpisodeState.ATTEMPT or bar.timeframe_s != 180:
            return
        if not bar.complete or bar.degraded or bar.instrument != self.zone.instrument or self.atr_prior_15m <= 0:
            return
        delta = bar.close - self.zone.boundary if self.zone.side == "RESISTANCE" else self.zone.boundary - bar.close
        if delta > 0 and delta >= Decimal("0.25") * self.atr_prior_15m:
            self.qualifying_end_ms = bar.end_ms
            self.confirmation_count = 0
            self._transition(EpisodeState.ACCEPTANCE_PENDING, bar.finalized_known_ms, "QUALIFYING_3M_CLOSE")

    def completed_1m(self, bar: Bar) -> None:
        if self.state != EpisodeState.ACCEPTANCE_PENDING or self.qualifying_end_ms is None:
            return
        if bar.timeframe_s != 60 or bar.instrument != self.zone.instrument:
            return
        expected_end = self.qualifying_end_ms + (self.confirmation_count + 1) * 60_000
        if bar.end_ms != expected_end or not bar.complete or bar.degraded:
            self._transition(EpisodeState.FAILED_ACCEPTANCE, bar.finalized_known_ms, "CONFIRMATION_TIMEOUT")
            return
        still_outside = bar.close > self.zone.boundary if self.zone.side == "RESISTANCE" else bar.close < self.zone.boundary
        if not still_outside:
            self._transition(EpisodeState.FAILED_ACCEPTANCE, bar.finalized_known_ms, "REENTERED_RANGE")
            return
        self.confirmation_count += 1
        if self.confirmation_count == 2:
            self._transition(EpisodeState.BREAKOUT_CONFIRMED_RESEARCH, bar.finalized_known_ms, "TWO_1M_CLOSES")

    def check_deadline(self, now_ms: int) -> None:
        if self.state == EpisodeState.ACCEPTANCE_PENDING and self.qualifying_end_ms is not None:
            if now_ms >= self.qualifying_end_ms + 180_000:
                self._transition(EpisodeState.EXPIRED, now_ms, "CONFIRMATION_TIMEOUT")


def option_quote_rejection(q: Optional[OptionQuote], now_ms: int, max_quote_age_ms: int, max_spread_ratio: Decimal) -> Optional[str]:
    """Thresholds are caller-supplied; R3 does not endorse numerical defaults."""
    if q is None or q.bid <= 0 or q.ask <= 0 or q.bid > q.ask or q.expiry_ms <= now_ms:
        return "OPTION_QUOTE_UNRELIABLE"
    if q.known_ms > now_ms or now_ms - q.known_ms > max_quote_age_ms:
        return "OPTION_QUOTE_UNRELIABLE"
    if q.size_at_ask <= 0 or q.size_at_bid <= 0:
        return "OPTION_LIQUIDITY_INSUFFICIENT"
    if (q.ask - q.bid) / ((q.ask + q.bid) / 2) > max_spread_ratio:
        return "OPTION_SPREAD_EXCESSIVE"
    return None


def research_snapshot(seq: int, episode: BreakoutEpisode, quality: Quality) -> dict:
    """One atomic chart/text snapshot; entry is always disabled in this reference."""
    return {
        "snapshot_seq": seq,
        "instrument": episode.zone.instrument,
        "source_quality": quality.value,
        "zone_id": episode.zone.zone_id,
        "zone_version": episode.zone.version,
        "known_ms": episode.known_ms,
        "chart_overlays": [{"id": episode.zone.zone_id, "version": episode.zone.version,
                            "boundary": str(episode.zone.boundary)}],
        "five_insights": {
            "market_trend": "UNDETERMINED",
            "opportunity_zone": episode.zone.zone_id,
            "price_behaviour": episode.state.value,
            "trade_guardian": "RESEARCH_ONLY",
            "trade_plan": "NO_VALID_TRADE",
        },
        "entry_eligible": False,
        "reject_reasons": ["ENTRY_POLICY_DISABLED"],
    }


@dataclass(frozen=True)
class StrikeObservation:
    quote: OptionQuote
    premium_return_3m: Decimal  # from timestamped same-contract observations
    volume_rate_ratio: Decimal  # against matching time-of-day reference
    oi_change_ratio: Optional[Decimal]  # participation only; direction not inferred
    delta: Optional[Decimal]


def rank_research_strikes(
    observations: list[StrikeObservation], now_ms: int,
    max_quote_age_ms: int, max_spread_ratio: Decimal,
) -> list[tuple[str, Decimal]]:
    """Illustrative ranking for research; weights NOT calibrated or tradable."""
    ranked: list[tuple[str, Decimal]] = []
    for o in observations:
        if option_quote_rejection(o.quote, now_ms, max_quote_age_ms, max_spread_ratio):
            continue
        # OI is intentionally excluded from directional score: increased OI
        # does not identify buyers versus sellers.
        score = o.premium_return_3m + o.volume_rate_ratio * Decimal("0.01")
        ranked.append((o.quote.contract, score))
    return sorted(ranked, key=lambda item: (-item[1], item[0]))
