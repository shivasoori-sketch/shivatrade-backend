"""Adviser anti-chart contract: badge steady on tick noise; book closes ≤ candles."""

from __future__ import annotations

import random

from thesis.book_engine import BookDivergenceEngine
from thesis.candle_builder import ClosedCandle1m
from thesis.thesis_engine import ThesisEngine
from thesis.types import BookOutput, BookSubScores, Direction, Ohlc, ThesisCondition, ThesisState, TradeThesis
from tests.conftest import make_tick


def _book(score: int = 70) -> BookOutput:
    return BookOutput(
        book_score=score,
        divergence_flag=False,
        sweep_risk=False,
        sub_scores=BookSubScores(50, 50, 50, 50),
        price_direction_up=True,
        oi_rising=False,
    )


def _thesis() -> TradeThesis:
    return TradeThesis(
        symbol="NSE:NOISE",
        direction=Direction.LONG,
        entry_price=100.0,
        stop_loss=95.0,
        target=110.0,
        book_score_baseline=70,
        dwell_seconds=300.0,
        conditions=[
            ThesisCondition("htf", "HTF trend still bullish", met=True),
            ThesisCondition("oi", "OI not rising — no new shorts", met=True),
            ThesisCondition("vol", "Volume follow-through sustained", met=True),
        ],
    )


def _candle(minute: int, close: float = 100.0) -> ClosedCandle1m:
    return ClosedCandle1m(
        minute_start=minute,
        ohlc=Ohlc(open=close, high=close + 0.5, low=close - 0.5, close=close),
        volume=120,
    )


def test_ten_thousand_ticks_no_confirmed_weakening_or_holds_flip() -> None:
    engine = ThesisEngine()
    thesis = _thesis()
    engine.register_trade("noise", thesis)
    rng = random.Random(42)
    confirmed_verdict_changes = 0
    last_confirmed_state = ThesisState.HOLDS

    for i in range(10_000):
        ltp = 99.0 + rng.random() * 2.0
        ts = 1_000.0 + i * 0.06
        out = engine.on_tick("noise", thesis, make_tick(ltp=ltp, ts=ts), _book())
        if out.confirmed and out.state != ThesisState.INVALIDATED:
            if out.state != last_confirmed_state:
                confirmed_verdict_changes += 1
                last_confirmed_state = out.state

    assert confirmed_verdict_changes == 0


def test_ten_minute_candles_badge_changes_at_most_once_when_stable() -> None:
    engine = ThesisEngine()
    thesis = _thesis()
    engine.register_trade("stable", thesis)
    states: list[ThesisState] = []

    for m in range(10):
        minute = 60_000 + m * 60
        tick = make_tick(ltp=100.0 + m * 0.01, ts=float(minute + 30))
        out = engine.on_candle_close(
            "stable",
            thesis,
            _candle(minute),
            tick,
            _book(),
        )
        if out.confirmed:
            states.append(out.state)

    unique = {s for s in states}
    assert len(unique) <= 1


def test_dwell_three_minutes_holds_six_minutes_weakening() -> None:
    engine = ThesisEngine()
    thesis = _thesis()
    engine.register_trade("dwell", thesis)
    false_one = [
        ThesisCondition("htf", "HTF trend still bullish", met=False),
        ThesisCondition("oi", "OI not rising — no new shorts", met=True),
        ThesisCondition("vol", "Volume follow-through sustained", met=True),
    ]
    engine.on_tick("dwell", thesis, make_tick(ltp=100.0, ts=0.0), _book(), updated_conditions=false_one)
    at_3m = engine.on_candle_close(
        "dwell",
        thesis,
        _candle(180),
        make_tick(ltp=100.0, ts=200.0),
        _book(),
        updated_conditions=false_one,
    )
    assert at_3m.state == ThesisState.HOLDS

    at_6m = engine.on_candle_close(
        "dwell",
        thesis,
        _candle(360),
        make_tick(ltp=100.0, ts=380.0),
        _book(),
        updated_conditions=false_one,
    )
    assert at_6m.state == ThesisState.WEAKENING


def test_book_candle_close_records_closed_candles() -> None:
    book_eng = BookDivergenceEngine()
    symbol = "NSE:BOOK"
    for i in range(100):
        book_eng.evaluate_tick(symbol, make_tick(ltp=100 + i * 0.01, ts=1000 + i))
    candle = ClosedCandle1m(
        minute_start=1980,
        ohlc=Ohlc(100, 101, 99.5, 100.5),
        volume=200,
    )
    book_eng.on_candle_close(symbol, candle, make_tick(ltp=100.5, ts=2001))
    assert len(book_eng._symbols[symbol].closed_candles) == 1
