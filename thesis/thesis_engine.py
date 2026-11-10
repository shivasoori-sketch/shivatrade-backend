"""THESIS conviction state machine — v2 candle-close authoritative."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from thesis.candle_builder import ClosedCandle1m
from thesis.types import (
    BookOutput,
    Direction,
    IntermediateSignal,
    ThesisCondition,
    ThesisOutput,
    ThesisState,
    TickInput,
    TradeThesis,
)


@dataclass
class ConditionTracker:
    condition_id: str
    false_since: float | None = None


@dataclass
class ThesisTradeRuntime:
    confirmed_state: ThesisState = ThesisState.HOLDS
    trackers: dict[str, ConditionTracker] = field(default_factory=dict)
    last_confirmed: ThesisOutput | None = None
    closed_candles: int = 0
    sweep_followthrough: int = 0
    sweep_confirmed: bool = False
    tick_log: list[str] = field(default_factory=list)


class ThesisEngine:
    """v2: INVALIDATED immediate on tick; other transitions on candle close."""

    def __init__(self) -> None:
        self._runtime: dict[str, ThesisTradeRuntime] = {}

    def register_trade(self, trade_id: str, thesis: TradeThesis) -> None:
        rt = ThesisTradeRuntime()
        for cond in thesis.conditions:
            rt.trackers[cond.id] = ConditionTracker(condition_id=cond.id)
        self._runtime[trade_id] = rt

    def step(
        self,
        trade_id: str,
        thesis: TradeThesis,
        tick: TickInput,
        book: BookOutput,
        *,
        updated_conditions: list[ThesisCondition] | None = None,
    ) -> ThesisOutput:
        """Backward-compatible entry: tick path only."""
        return self.on_tick(
            trade_id, thesis, tick, book, updated_conditions=updated_conditions
        )

    def on_tick(
        self,
        trade_id: str,
        thesis: TradeThesis,
        tick: TickInput,
        book: BookOutput,
        *,
        updated_conditions: list[ThesisCondition] | None = None,
    ) -> ThesisOutput:
        rt = self._runtime.setdefault(trade_id, ThesisTradeRuntime())
        conditions = list(updated_conditions or thesis.conditions)
        self._track_conditions(rt, conditions, tick.timestamp)

        if rt.confirmed_state == ThesisState.INVALIDATED:
            return self._emit(rt, rt.confirmed_state, conditions, book, (), confirmed=False)

        if self._stop_or_target_hit(thesis, tick):
            reasons = ("stop_loss_touched",) if (
                (thesis.direction == Direction.LONG and tick.ltp <= thesis.stop_loss)
                or (thesis.direction == Direction.SHORT and tick.ltp >= thesis.stop_loss)
            ) else ("target_reached_exit_signal",)
            return self._confirm(
                rt,
                ThesisState.INVALIDATED,
                conditions,
                book,
                reasons,
                tick_timestamp=tick.timestamp,
            )

        if self._core_structure_broken(thesis, tick, conditions):
            return self._confirm(
                rt,
                ThesisState.INVALIDATED,
                conditions,
                book,
                ("core_structure_broken",),
                tick_timestamp=tick.timestamp,
            )

        base = rt.last_confirmed or self._base_output(rt, conditions, book)
        return replace(base, confirmed=False)

    def on_candle_close(
        self,
        trade_id: str,
        thesis: TradeThesis,
        candle: ClosedCandle1m,
        tick: TickInput,
        book: BookOutput,
        *,
        updated_conditions: list[ThesisCondition] | None = None,
    ) -> ThesisOutput:
        rt = self._runtime.setdefault(trade_id, ThesisTradeRuntime())
        conditions = list(updated_conditions or thesis.conditions)
        rt.closed_candles += 1
        if book.sweep_risk:
            rt.sweep_followthrough += 1
        else:
            rt.sweep_followthrough = 0

        if rt.confirmed_state == ThesisState.INVALIDATED:
            return self._emit(rt, ThesisState.INVALIDATED, conditions, book, (), confirmed=True, minute=candle.minute_start)

        support = thesis.entry_price
        intermediate = self._intermediate_signal(
            thesis, candle, tick, book, rt, support=support
        )
        annotation = self._annotation_for_intermediate(intermediate)

        if (
            book.sweep_risk
            and rt.sweep_followthrough >= 1
            and self._conditions_support_hold(thesis, conditions, tick)
        ):
            if rt.sweep_followthrough >= 2:
                rt.sweep_confirmed = True
                annotation = "sweep detected, no follow-through"
                intermediate = None
            state = ThesisState.HOLDS
            reasons: tuple[str, ...] = ("sweep_confirmed_thesis_intact",)
            decision = "HOLD · sweep detected, no follow-through"
            out = self._pack(
                state,
                reasons,
                decision,
                conditions,
                annotation=annotation,
                intermediate=intermediate,
                confirmed=True,
                minute=candle.minute_start,
            )
            rt.confirmed_state = state
            rt.last_confirmed = out
            return out

        state = ThesisState.HOLDS
        reasons_list: list[str] = []

        false_count = sum(1 for c in conditions if not c.met)
        dwell_breach = self._dwell_breach(rt, thesis.dwell_seconds, tick.timestamp)
        book_weakening = self._book_baseline_drop(thesis, tick, book, conditions)

        if false_count >= 2:
            state = ThesisState.WEAKENING
            reasons_list.append("multiple_conditions_false")
        elif dwell_breach:
            state = ThesisState.WEAKENING
            reasons_list.append("condition_false_past_dwell")
        elif book_weakening:
            state = ThesisState.WEAKENING
            reasons_list.append("book_score_drop_below_baseline")

        decision = self._decision_line(state, book, conditions, reasons_list, annotation)
        out = self._pack(
            state,
            tuple(reasons_list),
            decision,
            conditions,
            annotation=annotation,
            intermediate=intermediate,
            confirmed=True,
            minute=candle.minute_start,
        )
        rt.confirmed_state = state
        rt.last_confirmed = out
        return out

    def _track_conditions(
        self, rt: ThesisTradeRuntime, conditions: list[ThesisCondition], now: float
    ) -> None:
        for cond in conditions:
            tracker = rt.trackers.setdefault(
                cond.id, ConditionTracker(condition_id=cond.id)
            )
            if cond.met:
                tracker.false_since = None
            elif tracker.false_since is None:
                tracker.false_since = now
                rt.tick_log.append(f"condition_false_once:{cond.id}")

    def _intermediate_signal(
        self,
        thesis: TradeThesis,
        candle: ClosedCandle1m,
        tick: TickInput,
        book: BookOutput,
        rt: ThesisTradeRuntime,
        *,
        support: float,
    ) -> IntermediateSignal | None:
        if rt.closed_candles < 1:
            return IntermediateSignal.INSUFFICIENT_DATA
        if book.sweep_risk:
            if rt.sweep_followthrough < 2:
                return IntermediateSignal.SWEEP_SUSPECTED
            return IntermediateSignal.SWEEP_SUSPECTED
        if thesis.direction == Direction.LONG:
            broke = candle.ohlc.close < support
            vol_ok = candle.volume > 0
            oi_rising = tick.oi > 0 and book.oi_rising
        else:
            broke = candle.ohlc.close > support
            vol_ok = candle.volume > 0
            oi_rising = book.oi_rising
        if broke and vol_ok and oi_rising:
            return IntermediateSignal.REAL_SELL_PRESSURE
        return None

    def _annotation_for_intermediate(
        self, signal: IntermediateSignal | None
    ) -> str:
        if signal == IntermediateSignal.SWEEP_SUSPECTED:
            return "observing: sweep suspected"
        if signal == IntermediateSignal.REAL_SELL_PRESSURE:
            return "observing: real sell pressure"
        if signal == IntermediateSignal.INSUFFICIENT_DATA:
            return "observing: insufficient data"
        return ""

    def _conditions_support_hold(
        self,
        thesis: TradeThesis,
        conditions: list[ThesisCondition],
        tick: TickInput,
    ) -> bool:
        if any(c.is_core and not c.met for c in conditions):
            return False
        if thesis.direction == Direction.LONG:
            return tick.ltp >= thesis.stop_loss
        return tick.ltp <= thesis.stop_loss

    def _confirm(
        self,
        rt: ThesisTradeRuntime,
        state: ThesisState,
        conditions: list[ThesisCondition],
        book: BookOutput,
        reasons: tuple[str, ...],
        *,
        tick_timestamp: float,
    ) -> ThesisOutput:
        decision = "EXIT" if state == ThesisState.INVALIDATED else self._decision_line(
            state, book, conditions, list(reasons), ""
        )
        out = self._pack(
            state,
            reasons,
            decision,
            conditions,
            confirmed=True,
            minute=int(tick_timestamp // 60) * 60,
        )
        rt.confirmed_state = state
        rt.last_confirmed = out
        return out

    def _emit(
        self,
        rt: ThesisTradeRuntime,
        state: ThesisState,
        conditions: list[ThesisCondition],
        book: BookOutput,
        reasons: tuple[str, ...],
        *,
        confirmed: bool,
        minute: int | None = None,
    ) -> ThesisOutput:
        base = rt.last_confirmed or self._base_output(rt, conditions, book)
        return replace(
            base,
            state=state,
            reasons=reasons or base.reasons,
            confirmed=confirmed,
            candle_minute_start=minute,
        )

    def _base_output(
        self,
        rt: ThesisTradeRuntime,
        conditions: list[ThesisCondition],
        book: BookOutput,
    ) -> ThesisOutput:
        return self._pack(
            rt.confirmed_state,
            (),
            self._decision_line(rt.confirmed_state, book, conditions, [], ""),
            conditions,
            confirmed=False,
        )

    def _pack(
        self,
        state: ThesisState,
        reasons: tuple[str, ...],
        decision: str,
        conditions: list[ThesisCondition],
        *,
        annotation: str = "",
        intermediate: IntermediateSignal | None = None,
        confirmed: bool,
        minute: int | None = None,
    ) -> ThesisOutput:
        return ThesisOutput(
            state=state,
            reasons=reasons,
            decision_line=decision,
            conditions=tuple(conditions),
            annotation=annotation,
            intermediate_signal=intermediate,
            confirmed=confirmed,
            candle_minute_start=minute,
        )

    def _stop_or_target_hit(self, thesis: TradeThesis, tick: TickInput) -> bool:
        if thesis.direction == Direction.LONG:
            return tick.ltp <= thesis.stop_loss or tick.ltp >= thesis.target
        return tick.ltp >= thesis.stop_loss or tick.ltp <= thesis.target

    def _core_structure_broken(
        self,
        thesis: TradeThesis,
        tick: TickInput,
        conditions: list[ThesisCondition],
    ) -> bool:
        for cond in conditions:
            if cond.is_core and not cond.met:
                return True
        if thesis.direction == Direction.LONG:
            return tick.ltp < tick.ohlc.low and tick.ltp < thesis.entry_price
        return tick.ltp > tick.ohlc.high and tick.ltp > thesis.entry_price

    def _dwell_breach(
        self, rt: ThesisTradeRuntime, dwell_seconds: float, now: float
    ) -> bool:
        for tracker in rt.trackers.values():
            if tracker.false_since is None:
                continue
            if now - tracker.false_since >= dwell_seconds:
                return True
        return False

    def _book_baseline_drop(
        self,
        thesis: TradeThesis,
        tick: TickInput,
        book: BookOutput,
        conditions: list[ThesisCondition],
    ) -> bool:
        drop = thesis.book_score_baseline - book.book_score
        if drop <= thesis.book_drop_weakening_pts:
            return False
        if thesis.direction == Direction.LONG:
            price_holds = tick.ltp >= thesis.entry_price * 0.998
        else:
            price_holds = tick.ltp <= thesis.entry_price * 1.002
        return price_holds and all(c.met or not c.is_core for c in conditions)

    def _decision_line(
        self,
        state: ThesisState,
        book: BookOutput,
        conditions: list[ThesisCondition],
        reasons: list[str],
        annotation: str,
    ) -> str:
        if state == ThesisState.INVALIDATED:
            return "EXIT"
        if state == ThesisState.WEAKENING:
            return "REDUCE · tighten stop"
        if "sweep detected" in annotation:
            return "HOLD · sweep detected, no follow-through"
        false_labels = [c.label for c in conditions if not c.met]
        if book.divergence_flag:
            watch = false_labels[0] if false_labels else "book divergence"
            return f"HOLD · watch {watch}"
        if false_labels:
            return f"HOLD · watch {false_labels[0]}"
        return "HOLD"
