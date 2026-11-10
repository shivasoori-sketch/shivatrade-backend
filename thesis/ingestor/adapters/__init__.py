"""Broker full-mode adapters (Phase 0 stubs mapped to spec §2.2)."""

from thesis.ingestor.adapters.upstox import UPSTOX_FULL_TICK_FIELDS, adapt_upstox_tick
from thesis.ingestor.adapters.zerodha import ZERODHA_FULL_TICK_FIELDS, adapt_zerodha_tick

__all__ = [
    "UPSTOX_FULL_TICK_FIELDS",
    "ZERODHA_FULL_TICK_FIELDS",
    "adapt_upstox_tick",
    "adapt_zerodha_tick",
]
