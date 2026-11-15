"""Friday 13 Nov 2026 session closes recorded by the Phase 0 audit.

The numbers are embedded fixtures. This module does not call an exchange,
a broker, or a market-data API. The exchange clock is last_trade_time.
The Saturday API response clock is stored beside it and is never the price time.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))
SESSION_DATE = "2026-11-13"
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "friday_13_nov_2026_closes.json"

_EXPECTED_KEYS = (
    ("NIFTY 50", "NSE_INDEX|Nifty 50"),
    ("BANKNIFTY", "NSE_INDEX|Nifty Bank"),
    ("SENSEX", "BSE_INDEX|SENSEX"),
)


@dataclass(frozen=True)
class HistoricalClose:
    instrument: str
    instrument_key: str
    close: Decimal
    close_text: str
    exchange_timestamp: datetime
    exchange_timestamp_text: str
    exchange_timestamp_ms: int
    session_date: str
    source: str
    price_basis: str
    audit_api_clock: datetime
    audit_api_clock_text: str


def unix_ms(moment: datetime) -> int:
    """Whole milliseconds since the Unix epoch, without float rounding."""
    if moment.tzinfo is None:
        raise ValueError("timestamp requires a timezone")
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    delta = moment.astimezone(timezone.utc) - epoch
    return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000


def _parse_ist(text: str) -> datetime:
    parsed = datetime.fromisoformat(text)
    if parsed.utcoffset() != timedelta(hours=5, minutes=30):
        raise ValueError("timestamp must be IST (+05:30)")
    emitted = (
        parsed.isoformat(timespec="milliseconds")
        if parsed.microsecond
        else parsed.isoformat(timespec="seconds")
    )
    if emitted != text:
        raise ValueError("timestamp text is not canonical IST")
    return parsed


def load_closes(path: Path | None = None) -> tuple[HistoricalClose, ...]:
    payload = json.loads((path or _FIXTURE).read_text(encoding="utf-8"))
    if payload.get("session_date") != SESSION_DATE:
        raise ValueError("fixture session date must be the Friday close")
    if payload.get("price_basis") != "SESSION_CLOSE":
        raise ValueError("fixture price basis must be the session close")
    source = payload.get("source")
    if source != "PHASE0_AUDIT_RECORDED_CLOSE":
        raise ValueError("fixture source is not the recorded Phase 0 close")
    audit_text = payload["audit_api_clock_ist"]
    audit_clock = _parse_ist(audit_text)
    if audit_clock.date().isoformat() != "2026-11-14":
        raise ValueError("audit API clock must stay on Saturday 14 Nov 2026")
    rows = payload["closes"]
    observed = [(row["instrument"], row["instrument_key"]) for row in rows]
    if observed != list(_EXPECTED_KEYS):
        raise ValueError("fixture must list NIFTY 50, BANKNIFTY, SENSEX in that order")
    loaded: list[HistoricalClose] = []
    for row in rows:
        for banned in ("quality", "entry_eligible", "side", "order"):
            if banned in row:
                raise ValueError(f"close record must not carry {banned}")
        close = Decimal(row["close"])
        if close <= 0 or str(close) != row["close"]:
            raise ValueError("close must be a positive canonical decimal")
        exchange = _parse_ist(row["exchange_last_trade_time_ist"])
        if exchange.date().isoformat() != SESSION_DATE:
            raise ValueError("exchange last_trade_time must be Friday 13 Nov 2026")
        if exchange <= datetime(2026, 11, 13, 15, 30, tzinfo=IST):
            raise ValueError("recorded print is not the session close")
        if exchange == audit_clock or exchange.date() == audit_clock.date():
            raise ValueError("exchange time must not be the Saturday API clock")
        loaded.append(
            HistoricalClose(
                instrument=row["instrument"],
                instrument_key=row["instrument_key"],
                close=close,
                close_text=row["close"],
                exchange_timestamp=exchange,
                exchange_timestamp_text=row["exchange_last_trade_time_ist"],
                exchange_timestamp_ms=unix_ms(exchange),
                session_date=SESSION_DATE,
                source=source,
                price_basis="SESSION_CLOSE",
                audit_api_clock=audit_clock,
                audit_api_clock_text=audit_text,
            )
        )
    return tuple(loaded)
