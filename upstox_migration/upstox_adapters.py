#!/usr/bin/env python3
"""Map Upstox ticks to ShivaTrade/THESIS schemas (shadow)."""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# PulseGuard / live cache symbol aliases (Upstox keys → Kite-style quote keys)
UPSTOX_TO_QUOTE_KEY = {
    "NSE_INDEX|Nifty 50": ("NSE", "NIFTY 50"),
    "NSE_INDEX|Nifty Bank": ("NSE", "NIFTY BANK"),
    "BSE_INDEX|SENSEX": ("BSE", "SENSEX"),
}


def synthetic_token(instrument_key: str) -> int:
    digest = hashlib.sha256(instrument_key.encode("utf-8")).hexdigest()
    return int(digest[:12], 16) % 9_000_000_000 + 1_000_000


def adapt_upstox_thesis_raw(instrument_key: str, tick: dict[str, Any]) -> dict[str, Any]:
    """THESIS capture raw block (mirrors thesis/ingestor/adapters/zerodha.py)."""
    ts = tick.get("timestamp")
    if isinstance(ts, datetime):
        ts_text = ts.astimezone(IST).isoformat()
    else:
        ts_text = str(ts or datetime.now(IST).isoformat())
    symbol = instrument_key_to_thesis_symbol(instrument_key)
    return {
        "symbol": symbol,
        "ltp": tick.get("ltp"),
        "ltq": tick.get("ltq") or 1,
        "volume_traded": tick.get("volume_traded"),
        "oi": tick.get("oi"),
        "tbq": tick.get("tbq"),
        "tsq": tick.get("tsq"),
        "timestamp": ts_text,
        "open": tick.get("open"),
        "high": tick.get("high"),
        "low": tick.get("low"),
        "close": tick.get("close"),
        "depth": tick.get("depth") or {},
        "_source": "upstox_full",
        "_instrument_key": instrument_key,
        "_ohlc_is_prior_day": False,
    }


def instrument_key_to_thesis_symbol(instrument_key: str) -> str:
    if "|" not in instrument_key:
        return instrument_key
    segment, name = instrument_key.split("|", 1)
    if "INDEX" in segment:
        if name.upper() in ("NIFTY 50", "NIFTY BANK"):
            exch = "NSE"
        elif name.upper() == "SENSEX":
            exch = "BSE"
        else:
            exch = segment.split("_", 1)[0]
        return f"{exch}:{name}"
    if "_FO" in segment or segment.endswith("FO"):
        return f"NSE:{name.replace(' ', '')}"
    return f"NSE:{name}"


def thesis_jsonl_row(instrument_key: str, tick: dict[str, Any], *, session_id: str | None = None) -> dict[str, Any]:
    raw = adapt_upstox_thesis_raw(instrument_key, tick)
    ts = tick.get("timestamp")
    if isinstance(ts, datetime):
        epoch = ts.astimezone(IST).timestamp()
    else:
        epoch = time.time()
    sid = session_id or datetime.now(IST).strftime("%Y%m%d")
    return {
        "symbol": raw["symbol"],
        "broker": "upstox",
        "session_id": sid,
        "mode": "full",
        "ts": epoch,
        "raw": raw,
    }


def adapt_live_cache_row(instrument_key: str, tick: dict[str, Any]) -> dict[str, Any]:
    exch, sym = UPSTOX_TO_QUOTE_KEY.get(
        instrument_key,
        (instrument_key.split("|", 1)[0].split("_")[0], instrument_key.split("|", 1)[-1]),
    )
    ts = tick.get("timestamp")
    if not isinstance(ts, datetime):
        ts = datetime.now(IST)
    received = ts.astimezone(timezone.utc) if hasattr(ts, "astimezone") else datetime.now(tz=timezone.utc)
    bid = ask = None
    depth = tick.get("depth")
    if isinstance(depth, dict):
        buy = depth.get("buy") or depth.get("bid") or []
        sell = depth.get("sell") or depth.get("ask") or []
        if buy and isinstance(buy[0], dict):
            bid = buy[0].get("price") or buy[0].get("bp")
        if sell and isinstance(sell[0], dict):
            ask = sell[0].get("price") or sell[0].get("sp")
    return {
        "exchange": exch,
        "tradingsymbol": sym,
        "expiry": "",
        "instrument_token": synthetic_token(instrument_key),
        "timestamp": received.astimezone(IST).isoformat(),
        "received_at": received.isoformat(),
        "ltp": tick.get("ltp"),
        "last_price": tick.get("ltp"),
        "volume": tick.get("volume_traded"),
        "oi": tick.get("oi"),
        "bid": bid,
        "ask": ask,
        "_source": "upstox_shadow",
        "_instrument_key": instrument_key,
    }


def fabric_bucket_row(
    *,
    instrument_key: str,
    bucket_start: datetime,
    open_: float,
    high: float,
    low: float,
    close: float,
    tick_count: int,
    half_bucket_ticks: list[int] | None = None,
) -> dict[str, Any]:
    """30-second stream bucket (matches capture_fabric.candle() fields)."""
    exch_sym = UPSTOX_TO_QUOTE_KEY.get(instrument_key)
    if exch_sym:
        exchange, symbol = exch_sym
    else:
        exchange, symbol = "NSE", instrument_key.split("|")[-1]
    end = bucket_start.replace(microsecond=0)  # caller sets +30s on end field
    return {
        "schema": "upstox.fabric.stream_bucket.v1",
        "instrument_key": instrument_key,
        "symbol": symbol,
        "exchange": exchange,
        "start": bucket_start.isoformat(),
        "end": (bucket_start.replace(second=bucket_start.second)).isoformat(),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "tick_count": tick_count,
        "half_bucket_ticks": half_bucket_ticks or [tick_count],
        "instrument_token": synthetic_token(instrument_key),
        "source": "upstox_ws_v3",
    }
