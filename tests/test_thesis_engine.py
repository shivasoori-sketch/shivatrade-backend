"""Golden-style tests for THESIS v2 state machine."""

from __future__ import annotations

from thesis.candle_builder import ClosedCandle1m
from thesis.thesis_engine import ThesisEngine
from thesis.types import (
    BookOutput,
    BookSubScores,
    Direction,
    IntermediateSignal,
    Ohlc,
    ThesisCondition,
    ThesisState,
    TradeThesis,
)
from tests.conftest import make_tick


def _book(score: int, *, divergence: bool = False, sweep: bool = False, oi_rising: bool = False) -> BookOutput:
    return BookOutput(
        book_score=score,
        divergence_flag=divergence,
        sweep_risk=sweep,
        sub_scores=BookSubScores(50, 50, 50, 50),
        price_direction_up=True,
        oi_rising=oi_rising,
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


def _candle(minute: int, ohlc: Ohlc, volume: int = 100) -> ClosedCandle1m:
    return ClosedCandle1m(minute_start=minute, ohlc=ohlc, volume=volume)


def test_tick_holds_until_candle_close_for_weakening() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    engine.register_trade("t2", thesis)
    updated = [
        ThesisCondition("htf", "HTF trend bullish", met=False),
        ThesisCondition("vwap", "Above VWAP", met=False),
        ThesisCondition("vol", "Breakout volume confirmed", met=True),
    ]
    tick = make_tick(ltp=101.0, ts=200.0)
    tick_out = engine.on_tick("t2", thesis, tick, _book(65), updated_conditions=updated)
    assert tick_out.confirmed is False
    assert tick_out.state == ThesisState.HOLDS

    candle = _candle(180, Ohlc(open=101, high=101.5, low=100.5, close=101))
    close_out = engine.on_candle_close(
        "t2", thesis, candle, tick, _book(65), updated_conditions=updated
    )
    assert close_out.confirmed is True
    assert close_out.state == ThesisState.WEAKENING
    assert "multiple_conditions_false" in close_out.reasons


def test_dwell_weakening_only_on_candle_close() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    thesis.dwell_seconds = 60.0
    engine.register_trade("t3", thesis)
    one_false = [
        ThesisCondition("htf", "HTF trend bullish", met=False),
        ThesisCondition("vwap", "Above VWAP", met=True),
        ThesisCondition("vol", "Breakout volume confirmed", met=True),
    ]
    tick_late = make_tick(ltp=100.4, ts=1000.0)
    engine.on_tick("t3", thesis, tick_late, _book(67), updated_conditions=one_false)
    tick_close = make_tick(ltp=100.3, ts=1070.0)
    late_tick = engine.on_tick("t3", thesis, tick_close, _book(67), updated_conditions=one_false)
    assert late_tick.state == ThesisState.HOLDS
    assert late_tick.confirmed is False

    candle = _candle(1020, Ohlc(open=100.4, high=100.5, low=100.2, close=100.3))
    late_close = engine.on_candle_close(
        "t3", thesis, candle, tick_close, _book(67), updated_conditions=one_false
    )
    assert late_close.state == ThesisState.WEAKENING
    assert "condition_false_past_dwell" in late_close.reasons


def test_immediate_invalidated_on_stop_loss() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    engine.register_trade("t5", thesis)
    tick = make_tick(ltp=97.5, ts=4000.0)
    out = engine.on_tick("t5", thesis, tick, _book(30))
    assert out.confirmed is True
    assert out.state == ThesisState.INVALIDATED
    assert out.decision_line == "EXIT"


def test_sweep_confirmed_stays_holds() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    engine.register_trade("sw", thesis)
    tick = make_tick(ltp=101.0, ts=5000.0)
    c1 = _candle(4980, Ohlc(100, 101, 99.5, 100.5))
    c2 = _candle(5040, Ohlc(100.5, 102, 100, 100.8), volume=50)
    c3 = _candle(5100, Ohlc(100.8, 102.5, 100.5, 101), volume=40)
    engine.on_candle_close("sw", thesis, c1, tick, _book(68))
    out2 = engine.on_candle_close("sw", thesis, c2, tick, _book(68, sweep=True))
    assert out2.intermediate_signal == IntermediateSignal.SWEEP_SUSPECTED
    out3 = engine.on_candle_close("sw", thesis, c3, tick, _book(68, sweep=True))
    assert out3.state == ThesisState.HOLDS
    assert "sweep detected" in out3.annotation


def test_golden_transition_log_v2() -> None:
    engine = ThesisEngine()
    thesis = _long_thesis()
    engine.register_trade("gold", thesis)
    timeline = [
        (100.0, 0.0, True, True, True),
        (100.5, 60.0, True, True, True),
        (101.0, 120.0, False, True, True),
        (100.8, 430.0, False, True, True),
        (97.0, 600.0, False, False, False),
    ]
    states: list[str] = []
    minute = 0
    for ltp, ts, htf, vwap, vol in timeline:
        conds = [
            ThesisCondition("htf", "HTF trend bullish", met=htf),
            ThesisCondition("vwap", "Above VWAP", met=vwap),
            ThesisCondition("vol", "Breakout volume confirmed", met=vol),
        ]
        tick = make_tick(ltp=ltp, ts=ts, vtt=1500, oi=100_000 + int(ts))
        tick_out = engine.on_tick("gold", thesis, tick, _book(60), updated_conditions=conds)
        if tick_out.confirmed:
            states.append(tick_out.state.value)
        else:
            candle = _candle(minute, Ohlc(ltp, ltp + 0.5, ltp - 0.5, ltp))
            minute += 60
            close_out = engine.on_candle_close(
                "gold", thesis, candle, tick, _book(60), updated_conditions=conds
            )
            states.append(close_out.state.value)
    assert states[-1] == "INVALIDATED"
    assert "WEAKENING" in states
