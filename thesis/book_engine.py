"""Book-Divergence Engine — tick fusion + v2 sweep_risk on candle close."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from thesis.candle_builder import ClosedCandle1m
from thesis.types import (
    BookOutput,
    BookSubScores,
    FusionWeights,
    TickInput,
)


def _clamp_score(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _total_depth_qty(tick: TickInput) -> int:
    bid = sum(level.qty for level in tick.depth_bid)
    ask = sum(level.qty for level in tick.depth_ask)
    return bid + ask


def _spread(tick: TickInput) -> float:
    if not tick.depth_bid or not tick.depth_ask:
        return 0.0
    return tick.depth_ask[0].price - tick.depth_bid[0].price


@dataclass
class SymbolBookState:
    prev_ltp: float | None = None
    prev_oi: int | None = None
    prev_vtt: int | None = None
    prev_book_score: int | None = None
    depth_baseline: float | None = None
    volume_baseline: float | None = None
    depth_pull_ticks: int = 0
    ltp_window: list[float] = field(default_factory=list)
    vtt_window: list[int] = field(default_factory=list)
    oi_window: list[int] = field(default_factory=list)
    closed_candles: list[ClosedCandle1m] = field(default_factory=list)

    def observe(self, tick: TickInput, *, window: int = 20) -> None:
        self.ltp_window.append(tick.ltp)
        self.vtt_window.append(tick.vtt)
        self.oi_window.append(tick.oi)
        if len(self.ltp_window) > window:
            self.ltp_window.pop(0)
        if len(self.vtt_window) > window:
            self.vtt_window.pop(0)
        if len(self.oi_window) > window:
            self.oi_window.pop(0)

        depth = float(_total_depth_qty(tick))
        if self.depth_baseline is None:
            self.depth_baseline = depth
        else:
            self.depth_baseline = 0.95 * self.depth_baseline + 0.05 * depth

        vol = float(tick.vtt)
        if self.volume_baseline is None:
            self.volume_baseline = vol
        else:
            self.volume_baseline = 0.9 * self.volume_baseline + 0.1 * vol


class BookDivergenceEngine:
    """Fuse absorption, liquidity vacuum, OI, and volume into book_score."""

    def __init__(
        self,
        weights: FusionWeights | None = None,
        *,
        depth_pull_ticks_required: int = 2,
    ) -> None:
        self.weights = weights or FusionWeights()
        self.depth_pull_ticks_required = depth_pull_ticks_required
        self._symbols: dict[str, SymbolBookState] = {}

    def _state(self, symbol: str) -> SymbolBookState:
        if symbol not in self._symbols:
            self._symbols[symbol] = SymbolBookState()
        return self._symbols[symbol]

    def evaluate(self, symbol: str, tick: TickInput) -> BookOutput:
        """Per-tick fusion; sweep_risk is finalized on candle close."""
        return self.evaluate_tick(symbol, tick)

    def evaluate_tick(self, symbol: str, tick: TickInput) -> BookOutput:
        state = self._state(symbol)
        state.observe(tick)

        price_up = (
            state.prev_ltp is not None and tick.ltp > state.prev_ltp
        ) or (state.prev_ltp is None and tick.ltp >= tick.ohlc.close)

        absorption = self._absorption(tick, price_up)
        liquidity = self._liquidity_vacuum(tick, state)
        oi_conf = self._oi_confirmation(tick, state, price_up)
        volume_ft = self._volume_follow_through(tick, state)

        w = self.weights
        fused = (
            volume_ft * w.volume
            + oi_conf * w.oi
            + absorption * w.absorption
            + liquidity * w.depth
        ) / 100.0
        book_score = _clamp_score(fused)

        divergence = False
        if state.prev_book_score is not None and state.prev_ltp is not None:
            book_falling = book_score < state.prev_book_score
            book_rising = book_score > state.prev_book_score
            price_falling = tick.ltp < state.prev_ltp
            price_rising = tick.ltp > state.prev_ltp
            divergence = (price_rising and book_falling) or (
                price_falling and book_rising
            )

        depth = float(_total_depth_qty(tick))
        baseline = state.depth_baseline or depth
        depth_ratio = depth / baseline if baseline > 0 else 1.0
        spread = _spread(tick)
        spread_wide = spread > max(0.02, tick.ltp * 0.0002) if tick.ltp > 0 else spread > 0

        if depth_ratio < 0.75 and spread_wide:
            state.depth_pull_ticks += 1
        else:
            state.depth_pull_ticks = 0

        oi_rising = state.prev_oi is not None and tick.oi > state.prev_oi
        oi_flat = (
            state.prev_oi is not None
            and tick.oi <= state.prev_oi + max(1, state.prev_oi // 100)
        )

        state.prev_ltp = tick.ltp
        state.prev_oi = tick.oi
        state.prev_vtt = tick.vtt
        state.prev_book_score = book_score

        return BookOutput(
            book_score=book_score,
            divergence_flag=divergence,
            sweep_risk=False,
            sub_scores=BookSubScores(
                absorption=absorption,
                liquidity_vacuum=liquidity,
                oi_confirmation=oi_conf,
                volume_follow_through=volume_ft,
            ),
            price_direction_up=price_up,
            oi_rising=oi_rising,
            volume_below_rolling=volume_ft <= 40,
        )

    def on_candle_close(
        self, symbol: str, candle: ClosedCandle1m, tick: TickInput
    ) -> BookOutput:
        """Re-evaluate tick fusion and apply v2 sweep_risk at candle boundary."""
        state = self._state(symbol)
        state.closed_candles.append(candle)
        if len(state.closed_candles) > 8:
            state.closed_candles.pop(0)

        base = self.evaluate_tick(symbol, tick)
        sweep = self._sweep_risk_at_close(state, candle, tick)
        vol_dry = self._volume_dry_at_close(state, candle)
        return replace(
            base,
            sweep_risk=sweep,
            volume_below_rolling=vol_dry,
        )

    def _sweep_risk_at_close(
        self,
        state: SymbolBookState,
        candle: ClosedCandle1m,
        tick: TickInput,
    ) -> bool:
        if len(state.closed_candles) < 2:
            return False
        prior = state.closed_candles[:-1]
        key_high = max(c.ohlc.high for c in prior)
        key_low = min(c.ohlc.low for c in prior)
        wick_up = candle.ohlc.high > key_high and candle.ohlc.close < key_high
        wick_down = candle.ohlc.low < key_low and candle.ohlc.close > key_low
        wick_break = wick_up or wick_down
        if not wick_break:
            return False
        vol_dry = self._volume_dry_at_close(state, candle)
        oi_flat = state.prev_oi is not None and tick.oi <= state.prev_oi + max(
            1, (state.prev_oi or 0) // 100
        )
        return vol_dry and oi_flat

    def _volume_dry_at_close(
        self, state: SymbolBookState, candle: ClosedCandle1m
    ) -> bool:
        if len(state.closed_candles) < 2:
            return False
        prior = [c.volume for c in state.closed_candles[:-1] if c.volume > 0]
        if not prior:
            return False
        avg = sum(prior) / len(prior)
        return candle.volume < avg * 0.85

    def _absorption(self, tick: TickInput, price_up: bool) -> int:
        total = tick.tbq + tick.tsq
        if total <= 0:
            return 50
        sell_heavy = tick.tsq > tick.tbq * 1.15
        buy_heavy = tick.tbq > tick.tsq * 1.15
        if sell_heavy and price_up:
            return 85
        if buy_heavy and not price_up:
            return 85
        if sell_heavy or buy_heavy:
            return 55
        return 45

    def _liquidity_vacuum(self, tick: TickInput, state: SymbolBookState) -> int:
        depth = float(_total_depth_qty(tick))
        baseline = state.depth_baseline or depth
        if baseline <= 0:
            return 50
        ratio = depth / baseline
        spread = _spread(tick)
        spread_bps = (spread / tick.ltp * 10_000) if tick.ltp > 0 else 0.0
        thin = max(0.0, min(1.0, 1.0 - ratio))
        wide = min(1.0, spread_bps / 15.0)
        severity = 0.65 * thin + 0.35 * wide
        return _clamp_score(100.0 * (1.0 - severity))

    def _oi_confirmation(
        self, tick: TickInput, state: SymbolBookState, price_up: bool
    ) -> int:
        if state.prev_oi is None:
            return 50
        delta = tick.oi - state.prev_oi
        if price_up and delta > 0:
            return 80
        if not price_up and delta < 0:
            return 80
        if delta == 0:
            return 40
        return 25

    def _volume_follow_through(
        self, tick: TickInput, state: SymbolBookState
    ) -> int:
        if len(state.vtt_window) < 3:
            return 50
        recent = state.vtt_window[-3:]
        peak = max(recent)
        last = recent[-1]
        baseline = state.volume_baseline or float(tick.vtt)
        if baseline <= 0:
            return 50
        spike = peak > baseline * 1.5
        sustained = last >= baseline * 0.85
        if spike and sustained:
            return 85
        if spike and not sustained:
            return 25
        if last >= baseline:
            return 65
        return 40
