"""Default session-watch thesis for public /kaaldrishti (validation, not user P&L)."""

from __future__ import annotations

import os

from thesis.runtime import ThesisRuntime
from thesis.registry import TradeRecord
from thesis.types import Direction, ThesisCondition, TradeThesis

SESSION_WATCH_MESSAGE = (
    "Session watch — validation thesis on live ingest symbol, not a locked user trade "
    "or marketed P&L."
)

DEFAULT_SYMBOL = os.environ.get("THESIS_SESSION_SYMBOL", "NSE:NIFTY26NOVFUT")
REF_PRICE = float(os.environ.get("THESIS_SESSION_REF_PRICE", "24000"))
SL_PAD = float(os.environ.get("THESIS_SESSION_SL_PTS", "50"))
TGT_PAD = float(os.environ.get("THESIS_SESSION_TGT_PTS", "100"))


def _levels_from_ltp(ltp: float) -> tuple[float, float, float]:
    entry = round(ltp, 1)
    stop = round(entry - SL_PAD, 1)
    target = round(entry + TGT_PAD, 1)
    return entry, stop, target


def _default_conditions() -> list[ThesisCondition]:
    return [
        ThesisCondition(
            "structure",
            "HTF structure supports session bias",
            met=True,
        ),
        ThesisCondition(
            "vwap",
            "Price holds above session VWAP",
            met=True,
        ),
        ThesisCondition(
            "vol",
            "Volume follow-through sustained",
            met=True,
        ),
    ]


def ensure_session_watch_trade(rt: ThesisRuntime | None = None) -> TradeRecord:
    rt = rt or ThesisRuntime.get()
    reg = rt.registry
    if reg.session_watch_trade_id:
        existing = reg.get(reg.session_watch_trade_id)
        if existing and existing.status == "active":
            return existing

    symbol = DEFAULT_SYMBOL
    tick = rt.store.latest_tick(symbol)
    if tick is None:
        for sym in reg._by_symbol:
            tick = rt.store.latest_tick(sym)
            if tick is not None:
                symbol = sym
                break
    ltp = tick.ltp if tick is not None else REF_PRICE
    entry, stop, target = _levels_from_ltp(ltp)
    conditions = _default_conditions()
    thesis = TradeThesis(
        symbol=symbol,
        direction=Direction.LONG,
        entry_price=entry,
        stop_loss=stop,
        target=target,
        book_score_baseline=50,
        dwell_seconds=300.0,
        conditions=conditions,
    )
    baseline = 50
    if tick is not None:
        book = rt.pipeline.book_engine.evaluate(symbol, tick)
        baseline = book.book_score
    rec = reg.create(thesis, conditions, book_score_baseline=baseline)
    rec.watch_kind = "session_watch"
    reg.session_watch_trade_id = rec.trade_id
    rt.pipeline.register_trade(rec.trade_id, thesis)
    if tick is not None:
        rt.pipeline.on_tick(symbol, tick)
        rec.last_thesis = None
    return rec
