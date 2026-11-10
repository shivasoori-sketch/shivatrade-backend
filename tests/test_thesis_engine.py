"""Golden-style tests for THESIS state machine."""

from __future__ import annotations

from thesis.book_engine import BookDivergenceEngine
from thesis.thesis_engine import ThesisEngine
from thesis.types import (
    BookOutput,
    BookSubScores,
    Direction,
    ThesisCondition,
    ThesisState,
    TradeThesis,
)
from tests.conftest import make_tick


def _book(score: int, *, divergence: bool = False, sweep: bool = False) -> BookOutput:
    return BookOutput(
        book_score=score,
        divergence_flag=divergence,
        sweep_risk=sweep,
        sub_scores=BookSubScores(50, 50, 50, 50),
        price_direction_up=True,
    )


def _long_thesis() -> TradeThesis:
    return TradeThesis(
        symbol="NSE:TEST",
        direction=Direction.LONG,
        entry_price=100.0,
        stop_loss=98.0,
        target=105.0,
        book_score_baseline=70,
        dwell_seconds=300.0,
        conditions=[
            ThesisCondition("htf", "HTF trend bullish", met=True),
            ThesisCondition("vwap", "Above VWAP", met=True),
            ThesisCondition("vol", "Breakout volume confirmed", met=True),
        ],
    )


def test_holds_when_all_conditions_met() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    engine.register_trade("t1", thesis)
    tick = make_tick(ltp=101.0, ts=100.0)
    out = engine.step("t1", thesis, tick, _book(68))
    assert out.state == ThesisState.HOLDS
    assert out.decision_line == "HOLD"


def test_weakening_two_conditions_false() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    engine.register_trade("t2", thesis)
    updated = [
        ThesisCondition("htf", "HTF trend bullish", met=False),
        ThesisCondition("vwap", "Above VWAP", met=False),
        ThesisCondition("vol", "Breakout volume confirmed", met=True),
    ]
    tick = make_tick(ltp=101.0, ts=200.0)
    out = engine.step("t2", thesis, tick, _book(65), updated_conditions=updated)
    assert out.state == ThesisState.WEAKENING
    assert "multiple_conditions_false" in out.reasons
    assert out.decision_line == "REDUCE · tighten stop"


def test_weakening_after_dwell_not_on_single_blip() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    thesis.dwell_seconds = 60.0
    engine.register_trade("t3", thesis)
    one_false = [
        ThesisCondition("htf", "HTF trend bullish", met=False),
        ThesisCondition("vwap", "Above VWAP", met=True),
        ThesisCondition("vol", "Breakout volume confirmed", met=True),
    ]
    tick_early = make_tick(ltp=100.5, ts=1000.0)
    early = engine.step("t3", thesis, tick_early, _book(68), updated_conditions=one_false)
    assert early.state == ThesisState.HOLDS

    tick_late = make_tick(ltp=100.4, ts=1070.0)
    late = engine.step("t3", thesis, tick_late, _book(67), updated_conditions=one_false)
    assert late.state == ThesisState.WEAKENING
    assert "condition_false_past_dwell" in late.reasons


def test_weakening_book_drop_below_baseline_while_price_holds() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    engine.register_trade("t4", thesis)
    tick = make_tick(ltp=100.8, ts=3000.0)
    out = engine.step("t4", thesis, tick, _book(35))
    assert out.state == ThesisState.WEAKENING
    assert "book_score_drop_below_baseline" in out.reasons


def test_invalidated_on_stop_loss() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    engine.register_trade("t5", thesis)
    tick = make_tick(ltp=97.5, ts=4000.0)
    out = engine.step("t5", thesis, tick, _book(30))
    assert out.state == ThesisState.INVALIDATED
    assert out.decision_line == "EXIT"
    assert "stop_loss_touched" in out.reasons


def test_invalidated_core_condition_broken() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    engine.register_trade("t6", thesis)
    core_broken = [
        ThesisCondition(
            "entry_low", "Above entry candle low", met=False, is_core=True
        ),
        ThesisCondition("vwap", "Above VWAP", met=True),
    ]
    thesis.conditions = core_broken
    tick = make_tick(ltp=99.5, ts=5000.0)
    out = engine.step("t6", thesis, tick, _book(60), updated_conditions=core_broken)
    assert out.state == ThesisState.INVALIDATED
    assert "core_structure_broken" in out.reasons


def test_golden_transition_log() -> None:
    """Byte-stable sequence for replay validation (synthetic)."""
    engine = ThesisEngine()
    book_engine = BookDivergenceEngine()
    thesis = _long_thesis()
    engine.register_trade("gold", thesis)
    symbol = thesis.symbol
    timeline = [
        (100.0, 0.0, True, True, True),
        (100.5, 60.0, True, True, True),
        (101.0, 120.0, False, True, True),
        (100.8, 430.0, False, True, True),
        (97.0, 600.0, False, False, False),
    ]
    states: list[str] = []
    for ltp, ts, htf, vwap, vol in timeline:
        conds = [
            ThesisCondition("htf", "HTF trend bullish", met=htf),
            ThesisCondition("vwap", "Above VWAP", met=vwap),
            ThesisCondition("vol", "Breakout volume confirmed", met=vol),
        ]
        tick = make_tick(ltp=ltp, ts=ts, vtt=1500, oi=100_000 + int(ts))
        book = book_engine.evaluate(symbol, tick)
        out = engine.step("gold", thesis, tick, book, updated_conditions=conds)
        states.append(out.state.value)
    assert states == ["HOLDS", "HOLDS", "HOLDS", "WEAKENING", "INVALIDATED"]
