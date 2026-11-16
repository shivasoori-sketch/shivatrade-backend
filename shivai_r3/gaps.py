"""Explicit holes from R3 section 14.

Each function records that the missing piece is still missing. None of them
scores a trade, writes a file, or opens a socket.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Sequence


@dataclass(frozen=True)
class Section14Gap:
    gap_id: str
    status: str
    note: str


@dataclass(frozen=True)
class StructureRead:
    label: str
    zone_ids: tuple[str, ...]
    implemented: bool


@dataclass(frozen=True)
class PremiumTargets:
    t1: Optional[str] = None
    t2: Optional[str] = None
    t3: Optional[str] = None


# Status values are the stage claim. They are not a production checklist tick.
GAPS: tuple[Section14Gap, ...] = (
    Section14Gap(
        "production_upstox_transport",
        "NOT_IMPLEMENTED",
        "No market-data client in this package.",
    ),
    Section14Gap(
        "bos_choch_detector",
        "NOT_IMPLEMENTED",
        "BOS/CHoCH is not implemented. Structure stays UNDETERMINED. A candle statistic is not structure.",
    ),
    Section14Gap(
        "atr_computation",
        "NOT_IMPLEMENTED",
        "ATR14 is not computed.",
    ),
    Section14Gap(
        "order_book_flow",
        "NOT_IMPLEMENTED",
        "Index depth is not a rejection and flow is not scored.",
    ),
    Section14Gap(
        "option_premium_projection",
        "NOT_IMPLEMENTED",
        "No premium target is projected.",
    ),
    Section14Gap(
        "risk_fee_model",
        "NOT_IMPLEMENTED",
        "No fee schedule. D16 numeric limits are open.",
    ),
    Section14Gap(
        "trade_guardian",
        "REFERENCE_SUBSET_ONLY",
        "The reference virtual stop remains irreversible. A close does not open a virtual position.",
    ),
    Section14Gap(
        "authenticated_live_ui",
        "NOT_BUILT",
        "No chart or insight page is served.",
    ),
    Section14Gap(
        "storage",
        "NOT_IMPLEMENTED",
        "Snapshots stay in memory.",
    ),
    Section14Gap(
        "public_deployment",
        "NOT_AUTHORIZED",
        "No route and no service unit.",
    ),
)

SWING_EVENT_FIXTURES_REQUIRED = 20
SETUP_B = "OUT_OF_SCOPE"
STAGE_A_LIVE_WINDOWS = "DEFERRED"
D16 = "OPEN"
PRODUCTION_COMPLETE = False
PUBLIC_ROUTE_AUTHORIZED = False


def swing_event_fixture_count() -> int:
    """Expected-event swing tapes shipped with this package. Still zero."""
    return 0


def structure_from_bars(bars: Sequence[object]) -> StructureRead:
    """BOS/CHoCH is not implemented. The tape is ignored on purpose."""
    _ = bars
    return StructureRead("UNDETERMINED", (), False)


def atr14_15m_prior(bars: Sequence[object]) -> Optional[Decimal]:
    """ATR computation is not implemented, including when 20 prior bars are present."""
    _ = bars
    return None


def index_depth_rejection(depth_levels: int) -> Optional[str]:
    """Missing index depth is not a rejection. Populated depth is still not flow."""
    _ = depth_levels
    return None


def order_book_flow() -> str:
    return "NOT_IMPLEMENTED"


def project_premium_targets() -> PremiumTargets:
    return PremiumTargets()


def persist_snapshot(snapshot: object, destination: object) -> str:
    """Refuses to write. The destination is not opened."""
    _ = (snapshot, destination)
    return "NOT_IMPLEMENTED"
