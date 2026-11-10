"""Zerodha/Kite full-mode adapter (spec §2.2) — OHLC is prior day; use LTP+LTQ for candles."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _ts_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    return value

ZERODHA_FULL_TICK_FIELDS = (
    "ltp",
    "ltq",
    "vtt",
    "tbq",
    "tsq",
    "oi",
    "depth",
    "timestamp",
)


def adapt_zerodha_tick(tick: dict[str, Any], *, symbol: str) -> dict[str, Any]:
    """
    Map KiteTicker full-mode tick to normalize_broker_tick input.

    Real-time OHLC on the wire is **previous day** — retained only for context;
    candle_builder must use LTP+LTQ, not these OHLC fields.
    """
    depth = tick.get("depth") or {}
    ohlc = tick.get("ohlc") or {}
    return {
        "symbol": symbol,
        "ltp": tick.get("last_price") or tick.get("ltp"),
        "ltq": tick.get("last_traded_quantity") or tick.get("ltq"),
        "volume_traded": tick.get("volume_traded") or tick.get("vtt"),
        "oi": tick.get("oi") or tick.get("open_interest"),
        "tbq": tick.get("total_buy_quantity") or tick.get("tbq"),
        "tsq": tick.get("total_sell_quantity") or tick.get("tsq"),
        "timestamp": _ts_value(
            tick.get("exchange_timestamp")
            or tick.get("timestamp")
            or tick.get("last_trade_time")
        ),
        "open": ohlc.get("open"),
        "high": ohlc.get("high"),
        "low": ohlc.get("low"),
        "close": ohlc.get("close"),
        "depth": depth,
        "_source": "zerodha_full",
        "_ohlc_is_prior_day": True,
    }
