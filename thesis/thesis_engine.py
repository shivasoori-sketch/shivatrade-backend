"""THESIS conviction state machine — deterministic, dwell-guarded."""

from __future__ import annotations

from dataclasses import dataclass, field

from thesis.types import (
    BookOutput,
    Direction,
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
class ThesisRuntime:
    state: ThesisState = ThesisState.HOLDS
    trackers: dict[str, ConditionTracker] = field(default_factory=dict)
    last_output: ThesisOutput | None = None


class ThesisEngine:
    """Evaluate thesis + book outputs into HOLDS | WEAKENING | INVALIDATED."""

    def __init__(self) -> None:
        self._runtime: dict[str, ThesisRuntime] = {}

    def register_trade(self, trade_id: str, thesis: TradeThesis) -> None:
        rt = ThesisRuntime()
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
        rt = self._runtime.setdefault(trade_id, ThesisRuntime())
        conditions = list(updated_conditions or thesis.conditions)

        for cond in conditions:
            tracker = rt.trackers.setdefault(
                cond.id, ConditionTracker(condition_id=cond.id)
            )
            if cond.met:
                tracker.false_since = None
            elif tracker.false_since is None:
                tracker.false_since = tick.timestamp

        reasons: list[str] = []
        state = ThesisState.HOLDS

        if self._stop_or_target_hit(thesis, tick):
            state = ThesisState.INVALIDATED
            if thesis.direction == Direction.LONG:
                if tick.ltp <= thesis.stop_loss:
                    reasons.append("stop_loss_touched")
                else:
                    reasons.append("target_reached_exit_signal")
            else:
                if tick.ltp >= thesis.stop_loss:
                    reasons.append("stop_loss_touched")
                else:
                    reasons.append("target_reached_exit_signal")
        elif self._core_structure_broken(thesis, tick, conditions):
            state = ThesisState.INVALIDATED
            reasons.append("core_structure_broken")
        else:
            false_count = sum(1 for c in conditions if not c.met)
            dwell_breach = self._dwell_breach(
                rt, thesis.dwell_seconds, tick.timestamp
            )
            book_weakening = self._book_baseline_drop(
                thesis, tick, book, conditions
            )

            if false_count >= 2:
                state = ThesisState.WEAKENING
                reasons.append("multiple_conditions_false")
            elif dwell_breach:
                state = ThesisState.WEAKENING
                reasons.append("condition_false_past_dwell")
            elif book_weakening:
                state = ThesisState.WEAKENING
                reasons.append("book_score_drop_below_baseline")

        decision = self._decision_line(state, book, conditions, reasons)
        output = ThesisOutput(
            state=state,
            reasons=tuple(reasons),
            decision_line=decision,
            conditions=tuple(conditions),
        )
        rt.state = state
        rt.last_output = output
        return output

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
            if not cond.is_core or cond.met:
                continue
            return True
        if thesis.direction == Direction.LONG:
            return tick.ltp < tick.ohlc.low and tick.ltp < thesis.entry_price
        return tick.ltp > tick.ohlc.high and tick.ltp > thesis.entry_price

    def _dwell_breach(
        self, rt: ThesisRuntime, dwell_seconds: float, now: float
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
    ) -> str:
        if state == ThesisState.INVALIDATED:
            return "EXIT"
        if state == ThesisState.WEAKENING:
            if book.sweep_risk and book.divergence_flag:
                return "REDUCE · tighten stop"
            return "REDUCE · tighten stop"
        false_labels = [c.label for c in conditions if not c.met]
        if book.divergence_flag:
            watch = false_labels[0] if false_labels else "book divergence"
            return f"HOLD · watch {watch}"
        if false_labels:
            return f"HOLD · watch {false_labels[0]}"
        return "HOLD"
