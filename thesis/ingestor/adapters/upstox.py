"""Upstox V3 full feed adapter (spec §2.2) — stub for capture + normalize."""

from __future__ import annotations

from typing import Any

# Canonical field set from THESIS v2 §2.2 (Upstox V3 full).
UPSTOX_FULL_TICK_FIELDS = (
    "ltpc",
    "marketLevel",
    "marketOHLC",
    "vtt",
    "oi",
    "tbq",
    "tsq",
    "timestamp",
)


def adapt_upstox_tick(msg: dict[str, Any], *, symbol: str) -> dict[str, Any]:
    """
  Map Upstox V3 full-mode payload into a dict suitable for normalize_broker_tick.

  Expected upstream shape (subset):
    ltpc: { ltp, ltq, cp, ... }
    marketLevel: { bid[], ask[] }  # 5-level depth
    marketOHLC: native multi-TF OHLC (not used for Zerodha-style builder)
    vtt, oi, tbq, tsq, timestamp
  """
    ltpc = msg.get("ltpc") or msg.get("fullFeed", {}).get("ltpc") or {}
    level = msg.get("marketLevel") or msg.get("fullFeed", {}).get("marketLevel") or {}

    bids = level.get("bid") or level.get("buy") or []
    asks = level.get("ask") or level.get("sell") or []

    ts = msg.get("timestamp") or msg.get("ts") or ltpc.get("ltt")
    return {
        "symbol": symbol,
        "ltp": ltpc.get("ltp") or ltpc.get("last_price"),
        "ltq": ltpc.get("ltq") or ltpc.get("ltt"),
        "vtt": msg.get("vtt") or msg.get("volumeTradedToday"),
        "oi": msg.get("oi") or msg.get("openInterest"),
        "tbq": msg.get("tbq") or msg.get("totalBuyQuantity"),
        "tsq": msg.get("tsq") or msg.get("totalSellQuantity"),
        "timestamp": ts,
        "marketOHLC": msg.get("marketOHLC"),
        "depth": {
            "buy": _depth_rows(bids),
            "sell": _depth_rows(asks),
        },
        "_source": "upstox_full",
    }


def _depth_rows(levels: list[Any]) -> list[dict[str, float | int]]:
    out: list[dict[str, float | int]] = []
    for row in (levels or [])[:5]:
        if isinstance(row, dict):
            out.append(
                {
                    "price": float(row.get("price") or row.get("p") or 0),
                    "quantity": int(row.get("quantity") or row.get("qty") or row.get("q") or 0),
                }
            )
    return out
