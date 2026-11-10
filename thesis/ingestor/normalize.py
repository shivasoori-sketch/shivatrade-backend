"""Normalize broker full-mode payloads into TickInput."""

from __future__ import annotations

from thesis.types import DepthLevel, Ohlc, TickInput


def _depth_side(levels: list[dict] | None) -> tuple[DepthLevel, ...]:
    if not levels:
        return ()
    out: list[DepthLevel] = []
    for row in levels[:5]:
        out.append(
            DepthLevel(
                price=float(row.get("price") or row.get("p") or 0),
                qty=int(row.get("quantity") or row.get("qty") or row.get("q") or 0),
            )
        )
    return tuple(out)


def normalize_broker_tick(raw: dict, *, symbol: str, timestamp: float | None = None) -> TickInput:
    """Accept Kite-style or generic dict ticks."""
    ltp = float(raw.get("last_price") or raw.get("ltp") or raw.get("last_traded_price") or 0)
    o = float(raw.get("open") or raw.get("ohlc", {}).get("open") or ltp)
    h = float(raw.get("high") or raw.get("ohlc", {}).get("high") or ltp)
    lo = float(raw.get("low") or raw.get("ohlc", {}).get("low") or ltp)
    c = float(raw.get("close") or raw.get("ohlc", {}).get("close") or ltp)
    ts = float(
        timestamp
        if timestamp is not None
        else raw.get("timestamp")
        or raw.get("exchange_timestamp")
        or raw.get("ts")
        or 0.0
    )
    depth = raw.get("depth") or {}
    bid = depth.get("buy") or depth.get("bid") or raw.get("depth_bid") or []
    ask = depth.get("sell") or depth.get("ask") or raw.get("depth_ask") or []

    ltpc = raw.get("ltpc") or {}
    ltq = int(
        raw.get("ltq")
        or raw.get("last_traded_quantity")
        or ltpc.get("ltq")
        or ltpc.get("ltt")
        or raw.get("last_quantity")
        or 0
    )

    return TickInput(
        ltp=ltp,
        ohlc=Ohlc(open=o, high=h, low=lo, close=c),
        ltq=ltq,
        vtt=int(raw.get("volume_traded") or raw.get("vtt") or raw.get("volume") or 0),
        tbq=int(raw.get("total_buy_quantity") or raw.get("tbq") or 0),
        tsq=int(raw.get("total_sell_quantity") or raw.get("tsq") or 0),
        oi=int(raw.get("oi") or raw.get("open_interest") or 0),
        depth_bid=_depth_side(bid if isinstance(bid, list) else list(bid)),
        depth_ask=_depth_side(ask if isinstance(ask, list) else list(ask)),
        timestamp=ts,
    )
