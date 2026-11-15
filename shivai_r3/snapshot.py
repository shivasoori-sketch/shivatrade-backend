"""R3 intelligence snapshot for the Friday session closes.

Every snapshot is CLOSED/HISTORICAL and DATA_STALE. entry_eligible stays
false. ENTRY_POLICY_DISABLED stays on. No order side is emitted.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, time
from decimal import Decimal
from typing import Optional

from shivai_r3.closes import IST, HistoricalClose, load_closes, unix_ms
from shivai_r3.gaps import (
    D16,
    GAPS,
    PRODUCTION_COMPLETE,
    PUBLIC_ROUTE_AUTHORIZED,
    SETUP_B,
    STAGE_A_LIVE_WINDOWS,
    PremiumTargets,
    Section14Gap,
    index_depth_rejection,
    project_premium_targets,
)
from shivai_r3.reference.shivai_core import option_quote_rejection

# Sunday 15 Nov 2026 13:04 IST. Stage clock for this build, not an exchange tick
# and not the Saturday 14 Nov 19:54 IST API response clock.
STAGE_ASSESSMENT_IST = "2026-11-15T13:04:00+05:30"
STAGE_ASSESSMENT = datetime(2026, 11, 15, 13, 4, tzinfo=IST)

CASH_SESSION_OPEN = time(9, 15, 0)
CASH_SESSION_CLOSE = time(15, 30, 0)
CANDIDATE_FREEZE = time(15, 0, 0)

# R3 section 10 / R2.1 section E. First match is the highlighted reason.
REJECTION_PRECEDENCE: tuple[str, ...] = (
    "MARKET_CLOSED",
    "SESSION_CUTOFF",
    "INSTRUMENT_UNSUPPORTED",
    "SPOT_FEED_UNVERIFIED",
    "FEED_UNAVAILABLE",
    "FEED_STALE",
    "FEED_DEGRADED",
    "RECOVERY_WARMUP",
    "TIMESTAMP_INVALID",
    "CANDLE_DEGRADED",
    "ATR_UNAVAILABLE",
    "ZONE_ID_MISSING",
    "ZONE_INVALIDATED",
    "STRUCTURE_CONFLICT",
    "CONFIRMATION_TIMEOUT",
    "REENTERED_RANGE",
    "OPTION_CONTRACT_UNAVAILABLE",
    "OPTION_EXPIRY_INVALID",
    "OPTION_QUOTE_UNRELIABLE",
    "OPTION_SPREAD_EXCESSIVE",
    "OPTION_LIQUIDITY_INSUFFICIENT",
    "OPTION_COST_MODEL_UNAVAILABLE",
    "VOLATILITY_EXCESSIVE",
    "RISK_LIMIT_MISSING",
    "RISK_LIMIT_BREACHED",
    "ENTRY_POLICY_DISABLED",
    "UNKNOWN_SAFETY_STATE",
)

ROW_TITLES: tuple[str, ...] = (
    "MARKET STRUCTURE",
    "MOVE OPPORTUNITY",
    "STRIKE INTELLIGENCE",
    "GUARDIAN STATUS",
    "PLAN / OUTCOME",
)


@dataclass(frozen=True)
class InsightRow:
    index: int
    title: str
    text: str
    detail: str
    assessment: str
    feed_quality: str
    primary_reject_reason: Optional[str] = None


@dataclass(frozen=True)
class Header:
    instrument: str
    price: str
    exchange_date: str
    source_quality: str
    last_valid_tick: Optional[str]
    last_exchange_print: str
    last_exchange_print_kind: str
    last_engine_assessment: str


@dataclass(frozen=True)
class Limits:
    production_complete: bool
    entry_eligible: bool
    entry_policy: str
    stage_a_live_windows: str
    setup_b: str
    d16: str
    public_route_authorized: bool
    authenticated_live_ui: str
    storage: str
    spot_feed: str


@dataclass(frozen=True)
class ClosedSnapshot:
    schema_name: str
    schema_version: str
    ruleset_id: str
    snapshot_seq: int
    instrument: str
    instrument_key: str
    session: str
    session_state: str
    epoch: str
    known_at: str
    known_at_ms: int
    exchange_timestamp: str
    exchange_timestamp_ms: int
    clock_domain: str
    audit_api_clock: str
    received_at: Optional[str]
    source: str
    price_basis: str
    header: Header
    assessment: str
    feed_quality: str
    quality_flags: tuple[str, ...]
    zone_ids_and_versions: tuple[str, ...]
    chart_overlays: tuple[str, ...]
    chart_timeframe: str
    chart_bars: tuple[str, ...]
    five_rows: tuple[InsightRow, ...]
    episode_id: Optional[str]
    virtual_trade_id: Optional[str]
    reject_reasons: tuple[str, ...]
    highlighted_reject_reason: str
    entry_eligible: bool
    entry_policy: str
    order_intent: str
    ranked_contracts: tuple[str, ...]
    targets: PremiumTargets
    depth_levels: int
    depth_rejection: Optional[str]
    structure_label: str
    limits: Limits
    section14_gaps: tuple[Section14Gap, ...]
    content_hash: str


def _clock(moment: datetime) -> time:
    return moment.timetz().replace(tzinfo=None)


def outside_regular_session(moment: datetime) -> bool:
    """Weekends and any clock outside 09:15–15:30 IST. Holiday calendar is not implemented."""
    if moment.weekday() >= 5:
        return True
    clock = _clock(moment)
    return clock < CASH_SESSION_OPEN or clock >= CASH_SESSION_CLOSE


def _order_reasons(selected: set[str]) -> tuple[str, ...]:
    unknown = selected.difference(REJECTION_PRECEDENCE)
    if unknown:
        raise ValueError("rejection is outside the closed set: " + ",".join(sorted(unknown)))
    return tuple(reason for reason in REJECTION_PRECEDENCE if reason in selected)


def closed_reject_reasons(close: HistoricalClose, assessment: datetime) -> tuple[str, ...]:
    """Reasons that apply to a recorded session close. D16 ages are not used."""
    if assessment.tzinfo is None or assessment < close.exchange_timestamp:
        raise ValueError("assessment cannot precede the exchange print")
    selected: set[str] = set()
    # The print itself is the session close, after 15:30 IST, so it is not a
    # regular-session observation. A later calendar day is closed as well.
    if (
        close.exchange_timestamp.date() != assessment.date()
        or outside_regular_session(close.exchange_timestamp)
        or outside_regular_session(assessment)
    ):
        selected.add("MARKET_CLOSED")
    # Freeze is read from the exchange print. Sunday afternoon is before 15:00
    # and is not what sets this flag.
    if _clock(close.exchange_timestamp) >= CANDIDATE_FREEZE:
        selected.add("SESSION_CUTOFF")
    # This package has no verified native spot stream. A prior close is not one.
    selected.add("SPOT_FEED_UNVERIFIED")
    selected.add("FEED_STALE")
    selected.add("ATR_UNAVAILABLE")
    selected.add("ZONE_ID_MISSING")
    selected.add("OPTION_CONTRACT_UNAVAILABLE")
    # Age and spread arguments are not D16 limits. The kernel returns before
    # reading them when the quote is absent.
    quote_reason = option_quote_rejection(
        None, unix_ms(assessment), 0, Decimal("0")
    )
    if quote_reason != "OPTION_QUOTE_UNRELIABLE":
        raise RuntimeError("absent option quote must stay unreliable")
    selected.add(quote_reason)
    selected.add("OPTION_COST_MODEL_UNAVAILABLE")
    selected.add("RISK_LIMIT_MISSING")
    selected.add("ENTRY_POLICY_DISABLED")
    if index_depth_rejection(0) is not None:
        raise RuntimeError("index depth must not become a rejection")
    return _order_reasons(selected)


def _rows(highlighted: str) -> tuple[InsightRow, ...]:
    assessment = "CLOSED/HISTORICAL"
    quality = "DATA_STALE"
    specs = (
        (1, "MARKET STRUCTURE", "UNDETERMINED", "No 1h or 15m regime. Session close only.", None),
        (2, "MOVE OPPORTUNITY", "NO CONFIRMED ZONE", "Setup B is out of scope.", None),
        (3, "STRIKE INTELLIGENCE", "NOT_AVAILABLE", "No option contract or quote was loaded.", None),
        (4, "GUARDIAN STATUS", "DATA_STALE", "No virtual position.", None),
        (5, "PLAN / OUTCOME", "NO VALID TRADE", highlighted, highlighted),
    )
    rows = tuple(
        InsightRow(
            index=index,
            title=title,
            text=text,
            detail=detail,
            assessment=assessment,
            feed_quality=quality,
            primary_reject_reason=reason,
        )
        for index, title, text, detail, reason in specs
    )
    if tuple(row.title for row in rows) != ROW_TITLES:
        raise RuntimeError("five insight rows drifted from the R3 titles")
    return rows


def _limits() -> Limits:
    return Limits(
        production_complete=PRODUCTION_COMPLETE,
        entry_eligible=False,
        entry_policy="ENTRY_POLICY_DISABLED",
        stage_a_live_windows=STAGE_A_LIVE_WINDOWS,
        setup_b=SETUP_B,
        d16=D16,
        public_route_authorized=PUBLIC_ROUTE_AUTHORIZED,
        authenticated_live_ui="NOT_BUILT",
        storage="NOT_IMPLEMENTED",
        spot_feed="UNVERIFIED",
    )


def to_plain(value: object) -> object:
    if hasattr(value, "__dataclass_fields__"):
        return {
            name: to_plain(getattr(value, name))
            for name in value.__dataclass_fields__  # type: ignore[attr-defined]
        }
    if isinstance(value, tuple):
        return [to_plain(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise TypeError(f"cannot serialize {type(value).__name__}")


def payload_hash(plain: dict) -> str:
    body = dict(plain)
    body.pop("content_hash", None)
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_closed_snapshot(
    close: HistoricalClose,
    snapshot_seq: int,
    assessment: datetime = STAGE_ASSESSMENT,
) -> ClosedSnapshot:
    if snapshot_seq < 1:
        raise ValueError("snapshot_seq starts at 1")
    reasons = closed_reject_reasons(close, assessment)
    highlighted = reasons[0]
    if highlighted != "MARKET_CLOSED":
        raise RuntimeError("a session close must highlight MARKET_CLOSED")
    targets = project_premium_targets()
    draft = ClosedSnapshot(
        schema_name="IntelligenceSnapshot",
        schema_version="r3.0-closed-historical",
        ruleset_id="R3.0-closed-historical-v1",
        snapshot_seq=snapshot_seq,
        instrument=close.instrument,
        instrument_key=close.instrument_key,
        session=close.session_date,
        session_state="CLOSED",
        epoch="CLOSED_HISTORICAL",
        known_at=assessment.isoformat(timespec="seconds"),
        known_at_ms=unix_ms(assessment),
        exchange_timestamp=close.exchange_timestamp_text,
        exchange_timestamp_ms=close.exchange_timestamp_ms,
        clock_domain="EXCHANGE_LAST_TRADE_TIME",
        audit_api_clock=close.audit_api_clock_text,
        received_at=None,
        source=close.source,
        price_basis=close.price_basis,
        header=Header(
            instrument=close.instrument,
            price=close.close_text,
            exchange_date=close.session_date,
            source_quality="DATA_STALE",
            last_valid_tick=None,
            last_exchange_print=close.exchange_timestamp_text,
            last_exchange_print_kind="SESSION_CLOSE",
            last_engine_assessment="CLOSED/HISTORICAL",
        ),
        assessment="CLOSED/HISTORICAL",
        feed_quality="DATA_STALE",
        quality_flags=("CLOSED/HISTORICAL", "DATA_STALE"),
        zone_ids_and_versions=(),
        chart_overlays=(),
        chart_timeframe="3m",
        chart_bars=(),
        five_rows=_rows(highlighted),
        episode_id=None,
        virtual_trade_id=None,
        reject_reasons=reasons,
        highlighted_reject_reason=highlighted,
        entry_eligible=False,
        entry_policy="ENTRY_POLICY_DISABLED",
        order_intent="NONE",
        ranked_contracts=(),
        targets=targets,
        depth_levels=0,
        depth_rejection=None,
        structure_label="UNDETERMINED",
        limits=_limits(),
        section14_gaps=GAPS,
        content_hash="",
    )
    plain = to_plain(draft)
    if not isinstance(plain, dict):
        raise RuntimeError("snapshot plain form must be an object")
    return replace(draft, content_hash=payload_hash(plain))


def build_closed_snapshots(
    assessment: datetime = STAGE_ASSESSMENT,
) -> tuple[ClosedSnapshot, ...]:
    closes = load_closes()
    return tuple(
        build_closed_snapshot(close, index, assessment)
        for index, close in enumerate(closes, start=1)
    )
