"""Section 1 view filled only from the reference kernel.

Unconditional reference outputs are read by calling ``research_snapshot``.
Zone id, chart overlay, and price behaviour from that call are discarded:
this package has not computed a zone, so those values are left empty.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from shivai_r3.closes import HistoricalClose, load_closes
from shivai_r3.reference.shivai_core import (
    BreakoutEpisode,
    Quality,
    Zone,
    research_snapshot,
)

# Section 1 selector labels, in that order. NIFTY is the fixture's NIFTY 50 close.
_SELECTOR = (
    ("NIFTY", "NIFTY 50"),
    ("BANKNIFTY", "BANKNIFTY"),
    ("SENSEX", "SENSEX"),
)

ROW_TITLES: tuple[str, ...] = (
    "MARKET STRUCTURE",
    "MOVE OPPORTUNITY",
    "STRIKE INTELLIGENCE",
    "TRADE GUARDIAN",
    "TRADE PLAN / OUTCOME",
)


@dataclass(frozen=True)
class InsightRow:
    title: str
    value: str


@dataclass(frozen=True)
class InstrumentView:
    instrument: str
    price: str
    exchange_date: str
    source_quality: str
    last_valid_tick: str
    last_engine_assessment: str
    chart_overlays: tuple[dict, ...]
    five_rows: tuple[InsightRow, ...]
    entry_eligible: bool
    reject_reasons: tuple[str, ...]
    snapshot_seq: int
    instrument_key: str
    # Friday daily OHLC, kept off the chart. A 3-minute series is separate and empty.
    candle: tuple[str, str, str, str] | None = None
    three_minute_bars: tuple[dict, ...] = ()


def _reference_constants() -> dict:
    """Call the reference snapshot once, then drop anything that came from the dummy zone."""
    episode = BreakoutEpisode(
        Zone("unused", 1, "UNUSED", Decimal("1"), "RESISTANCE", 0),
        Decimal("1"),
    )
    return research_snapshot(0, episode, Quality.STALE)


def _rows(snapshot: dict) -> tuple[InsightRow, ...]:
    insights = snapshot["five_insights"]
    # Row 2 is the zone id in the reference. No zone was computed, so the cell stays empty.
    # Row 3 has no field on the reference snapshot. An empty ranking is empty.
    values = (
        insights["market_trend"],
        "",
        "",
        insights["trade_guardian"],
        insights["trade_plan"],
    )
    return tuple(InsightRow(title, value) for title, value in zip(ROW_TITLES, values, strict=True))


def _view(
    instrument: str,
    price: str,
    exchange_date: str,
    source_quality: str,
    snapshot: dict,
    instrument_key: str,
    candle: tuple[str, str, str, str] | None = None,
) -> InstrumentView:
    if source_quality == Quality.LIVE_VERIFIED.value:
        raise ValueError("source_quality cannot be the verified state")
    # No three_minute_bars.json exists in this package. Do not turn the daily OHLC into bars.
    return InstrumentView(
        instrument=instrument,
        price=price,
        exchange_date=exchange_date,
        source_quality=source_quality,
        last_valid_tick="",
        last_engine_assessment="",
        chart_overlays=(),
        five_rows=_rows(snapshot),
        entry_eligible=snapshot["entry_eligible"],
        reject_reasons=tuple(snapshot["reject_reasons"]),
        snapshot_seq=snapshot["snapshot_seq"],
        instrument_key=instrument_key,
        candle=candle,
        three_minute_bars=(),
    )


def close_views() -> tuple[InstrumentView, ...]:
    """Friday closes. source_quality is the reference value STALE."""
    snapshot = _reference_constants()
    by_name = {close.instrument: close for close in load_closes()}
    views: list[InstrumentView] = []
    for label, fixture_name in _SELECTOR:
        close: HistoricalClose = by_name[fixture_name]
        views.append(
            _view(
                label,
                close.close_text,
                close.exchange_timestamp.date().isoformat(),
                Quality.STALE.value,
                snapshot,
                close.instrument_key,
                (close.open_text, close.high_text, close.low_text, close.close_text),
            )
        )
    return tuple(views)


def session_views() -> tuple[InstrumentView, ...]:
    """Same layout for a session whose socket is not proven. Reference quality DEGRADED.

    Price, exchange date, last valid tick, and last engine assessment stay empty.
    A proven socket is not a state this package can enter.
    """
    snapshot = _reference_constants()
    by_name = {close.instrument: close for close in load_closes()}
    return tuple(
        _view(
            label,
            "",
            "",
            Quality.DEGRADED.value,
            snapshot,
            by_name[fixture_name].instrument_key,
        )
        for label, fixture_name in _SELECTOR
    )


def to_plain(view: InstrumentView) -> dict:
    return {
        "instrument": view.instrument,
        "price": view.price,
        "exchange_date": view.exchange_date,
        "source_quality": view.source_quality,
        "last_valid_tick": view.last_valid_tick,
        "last_engine_assessment": view.last_engine_assessment,
        "snapshot_seq": view.snapshot_seq,
        "instrument_key": view.instrument_key,
        "chart_overlays": list(view.chart_overlays),
        "candle": list(view.candle) if view.candle else None,
        "three_minute_bars": list(view.three_minute_bars),
        "five_rows": [{"title": row.title, "value": row.value} for row in view.five_rows],
        "entry_eligible": view.entry_eligible,
        "reject_reasons": list(view.reject_reasons),
    }
