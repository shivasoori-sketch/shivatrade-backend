"""Section 1 view filled only from the reference kernel.

Unconditional reference outputs are read by calling ``research_snapshot``.
Zone id, chart overlay, and price behaviour from that call are discarded:
this package has not computed a zone, so those values are left empty.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

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


_BAR_TOKEN = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
_THREE_MINUTE = Path(__file__).resolve().parent / "fixtures" / "three_minute_2026_11_13.json"
THREE_MINUTE_PATH = _THREE_MINUTE


@dataclass(frozen=True)
class ThreeMinuteBar:
    time_ist: str
    unix_s: int
    open: str
    high: str
    low: str
    close: str


@dataclass(frozen=True)
class ThreeMinuteSession:
    snapshot_seq: int
    session_date: str
    bars: dict[str, tuple[ThreeMinuteBar, ...]]


@dataclass(frozen=True)
class RestQuote:
    last_price: str
    observation_time: str
    last_trade_time: str
    quote_age: str


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
    # Friday daily OHLC, kept off the chart. three_minute_bars is the API series.
    candle: tuple[str, str, str, str] | None = None
    three_minute_bars: tuple[ThreeMinuteBar, ...] = ()
    source: str = ""
    observation_time: str = ""
    last_trade_time: str = ""
    quote_age: str = ""


def _reference_constants(seq: int = 0) -> dict:
    """Call the reference snapshot once, then drop anything that came from the dummy zone."""
    episode = BreakoutEpisode(
        Zone("unused", 1, "UNUSED", Decimal("1"), "RESISTANCE", 0),
        Decimal("1"),
    )
    return research_snapshot(seq, episode, Quality.STALE)


def _rows(snapshot: dict, bars: tuple[ThreeMinuteBar, ...] = ()) -> tuple[InsightRow, ...]:
    insights = snapshot["five_insights"]
    # Close versus the first open is a candle statistic, not confirmed structure.
    structure = insights["market_trend"]
    if bars:
        # No zone id and no strike ranking. Both stay RESEARCH_ONLY.
        opportunity = "RESEARCH_ONLY"
        strike = "RESEARCH_ONLY"
    else:
        structure = insights["market_trend"]
        opportunity = ""
        strike = ""
    values = (
        structure,
        opportunity,
        strike,
        insights["trade_guardian"],
        insights["trade_plan"],
    )
    return tuple(InsightRow(title, value) for title, value in zip(ROW_TITLES, values, strict=True))


def load_three_minute_bars() -> ThreeMinuteSession:
    """Last cash session returned by the historical 3-minute call. No other days."""
    payload = json.loads(_THREE_MINUTE.read_text(encoding="utf-8"))
    return parse_session_payload(payload)


def parse_session_payload(payload: dict) -> ThreeMinuteSession:
    """Validate one stored session. Raises instead of repairing a bar."""
    session_date = payload["session_date"]
    series = payload["series"]
    seq = payload.get("snapshot_seq", 0)
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise ValueError("snapshot_seq is not a count")
    if set(series) != {close.instrument_key for close in load_closes()}:
        raise ValueError("3-minute series keys do not match the three indexes")
    daily = {
        close.instrument_key: (close.open_text, close.high_text, close.low_text, close.close_text)
        for close in load_closes()
    }
    loaded: dict[str, tuple[ThreeMinuteBar, ...]] = {}
    for key, rows in series.items():
        bars: list[ThreeMinuteBar] = []
        for row in rows:
            if len(row) != 7:
                raise ValueError("3-minute row is missing a field")
            stamp, open_, high, low, close, _volume, _oi = row
            if not stamp.startswith(session_date + "T") or not stamp.endswith("+05:30"):
                raise ValueError("3-minute bar is outside the returned session")
            for token in (open_, high, low, close):
                if not isinstance(token, str) or _BAR_TOKEN.fullmatch(token) is None:
                    raise ValueError("3-minute price is not a decimal token")
            prices = (open_, high, low, close)
            if prices == daily[key]:
                raise ValueError("daily OHLC cannot be plotted as a 3-minute bar")
            o, h, l, c = (Decimal(token) for token in prices)
            if h < max(o, c) or l > min(o, c) or l > h:
                raise ValueError("3-minute bar breaks high or low")
            unix_s = int(datetime.fromisoformat(stamp).timestamp())
            bars.append(ThreeMinuteBar(stamp, unix_s, open_, high, low, close))
        bars.sort(key=lambda bar: bar.unix_s)
        if len(bars) < 2 or len({bar.unix_s for bar in bars}) != len(bars):
            raise ValueError("3-minute session is not a series")
        for earlier, later in zip(bars, bars[1:]):
            if later.unix_s - earlier.unix_s != 180:
                raise ValueError("3-minute bars are not 180 seconds apart")
        loaded[key] = tuple(bars)
    return ThreeMinuteSession(seq, session_date, loaded)


def _view(
    instrument: str,
    price: str,
    exchange_date: str,
    source_quality: str,
    snapshot: dict,
    instrument_key: str,
    candle: tuple[str, str, str, str] | None = None,
    bars: tuple[ThreeMinuteBar, ...] = (),
    source: str = "",
    observation_time: str = "",
    last_trade_time: str = "",
    quote_age: str = "",
) -> InstrumentView:
    if source_quality == Quality.LIVE_VERIFIED.value:
        raise ValueError("source_quality cannot be the verified state")
    return InstrumentView(
        instrument=instrument,
        price=price,
        exchange_date=exchange_date,
        source_quality=source_quality,
        last_valid_tick="",
        last_engine_assessment="RESEARCH_ONLY" if bars else "",
        chart_overlays=(),
        five_rows=_rows(snapshot, bars),
        entry_eligible=snapshot["entry_eligible"],
        reject_reasons=tuple(snapshot["reject_reasons"]),
        snapshot_seq=snapshot["snapshot_seq"],
        instrument_key=instrument_key,
        candle=candle,
        three_minute_bars=bars,
        source=source,
        observation_time=observation_time,
        last_trade_time=last_trade_time,
        quote_age=quote_age,
    )


def live_session_views() -> tuple[InstrumentView, ...]:
    """Empty Tuesday session. Stored candles are not attached."""
    snapshot = _reference_constants()
    if snapshot["entry_eligible"] is not False:
        raise ValueError("entry must stay disabled")
    if tuple(snapshot["reject_reasons"]) != ("ENTRY_POLICY_DISABLED",):
        raise ValueError("entry policy changed")
    insights = snapshot["five_insights"]
    if (
        insights["market_trend"] != "UNDETERMINED"
        or insights["trade_guardian"] != "RESEARCH_ONLY"
        or insights["trade_plan"] != "NO_VALID_TRADE"
    ):
        raise ValueError("reference rows changed")
    rows = tuple(
        InsightRow(title, value)
        for title, value in zip(
            ROW_TITLES,
            ("UNDETERMINED", "RESEARCH_ONLY", "RESEARCH_ONLY", "RESEARCH_ONLY", "NO_VALID_TRADE"),
            strict=True,
        )
    )
    names = (
        ("NIFTY", "NSE_INDEX|Nifty 50"),
        ("BANKNIFTY", "NSE_INDEX|Nifty Bank"),
        ("SENSEX", "BSE_INDEX|SENSEX"),
    )
    return tuple(
        InstrumentView(
            instrument=instrument,
            price="",
            exchange_date="2026-11-17",
            source_quality="STALE",
            last_valid_tick="",
            last_engine_assessment="",
            chart_overlays=(),
            five_rows=rows,
            entry_eligible=False,
            reject_reasons=("ENTRY_POLICY_DISABLED",),
            snapshot_seq=snapshot["snapshot_seq"],
            instrument_key=key,
            source="UPSTOX WEBSOCKET",
        )
        for instrument, key in names
    )


def degraded_rest_views(quotes: dict[str, RestQuote]) -> tuple[InstrumentView, ...]:
    """REST quote in the header. Friday bars stay the chart and gain no candle."""
    session = load_three_minute_bars()
    snapshot = _reference_constants(session.snapshot_seq)
    by_name = {close.instrument: close for close in load_closes()}
    views: list[InstrumentView] = []
    for label, fixture_name in _SELECTOR:
        close: HistoricalClose = by_name[fixture_name]
        quote = quotes[close.instrument_key]
        if _BAR_TOKEN.fullmatch(quote.last_price) is None:
            raise ValueError("REST last price is not a decimal")
        bars = session.bars[close.instrument_key]
        views.append(
            _view(
                label,
                quote.last_price,
                bars[-1].time_ist[:10],
                Quality.DEGRADED.value,
                snapshot,
                close.instrument_key,
                (close.open_text, close.high_text, close.low_text, close.close_text),
                bars,
                source="UPSTOX REST",
                observation_time=quote.observation_time,
                last_trade_time=quote.last_trade_time,
                quote_age=quote.quote_age,
            )
        )
    return tuple(views)


def close_views() -> tuple[InstrumentView, ...]:
    """Friday closes. source_quality is the reference value STALE."""
    by_name = {close.instrument: close for close in load_closes()}
    session = load_three_minute_bars()
    snapshot = _reference_constants(session.snapshot_seq)
    views: list[InstrumentView] = []
    for label, fixture_name in _SELECTOR:
        close: HistoricalClose = by_name[fixture_name]
        bars = session.bars[close.instrument_key]
        last = bars[-1]
        views.append(
            _view(
                label,
                last.close,
                last.time_ist[:10],
                Quality.STALE.value,
                snapshot,
                close.instrument_key,
                (close.open_text, close.high_text, close.low_text, close.close_text),
                bars,
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
        "three_minute_bars": [
            {
                "time_ist": bar.time_ist,
                "unix_s": bar.unix_s,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
            }
            for bar in view.three_minute_bars
        ],
        "five_rows": [{"title": row.title, "value": row.value} for row in view.five_rows],
        "entry_eligible": view.entry_eligible,
        "reject_reasons": list(view.reject_reasons),
    }
