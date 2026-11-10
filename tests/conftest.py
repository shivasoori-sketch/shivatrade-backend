"""Shared THESIS test fixtures."""

from __future__ import annotations

import pytest

from thesis.runtime import ThesisRuntime
from thesis.types import DepthLevel, Ohlc, TickInput


@pytest.fixture(autouse=True)
def _isolated_thesis_runtime() -> None:
    """Reset shared runtime unless a module opts out with its own fixture."""
    yield


def make_tick(
    *,
    ltp: float,
    ts: float,
    vtt: int = 1000,
    tbq: int = 5000,
    tsq: int = 4000,
    oi: int = 100_000,
    bid_qty: int = 800,
    ask_qty: int = 750,
    spread: float = 0.05,
    ohlc: Ohlc | None = None,
) -> TickInput:
    o = ohlc or Ohlc(open=ltp - 1, high=ltp + 2, low=ltp - 3, close=ltp - 0.5)
    depth_bid = tuple(
        DepthLevel(price=ltp - spread / 2 - i * 0.05, qty=max(1, bid_qty - i * 50))
        for i in range(5)
    )
    depth_ask = tuple(
        DepthLevel(price=ltp + spread / 2 + i * 0.05, qty=max(1, ask_qty - i * 50))
        for i in range(5)
    )
    return TickInput(
        ltp=ltp,
        ohlc=o,
        vtt=vtt,
        tbq=tbq,
        tsq=tsq,
        oi=oi,
        depth_bid=depth_bid,
        depth_ask=depth_ask,
        timestamp=ts,
    )
