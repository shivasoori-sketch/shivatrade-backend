"""3-minute candles from exchange timestamps. No network and no stored session."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
SESSION_DATE = date(2026, 11, 17)
BUCKET_MINUTES = 3
_CENT = Decimal("0.01")
_TOKEN = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
INDEXES = (
    ("NIFTY", "NSE_INDEX|Nifty 50"),
    ("BANKNIFTY", "NSE_INDEX|Nifty Bank"),
    ("SENSEX", "BSE_INDEX|SENSEX"),
)
_BY_KEY = {key: name for name, key in INDEXES}


@dataclass
class Candle:
    start: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    ticks: int


def as_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, str):
        number = Decimal(value.strip())
    elif isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("price is not a decimal")
    elif isinstance(value, int):
        number = Decimal(value)
    else:
        number = Decimal(str(value))
    if not number.is_finite() or number <= 0:
        raise ValueError("price is not a decimal")
    return number.quantize(_CENT, rounding=ROUND_HALF_UP)


def price_token(value: Decimal) -> str:
    token = format(value.quantize(_CENT, rounding=ROUND_HALF_UP), "f")
    if "." in token:
        token = token.rstrip("0").rstrip(".")
    if _TOKEN.fullmatch(token) is None:
        raise ValueError("price is not a decimal")
    return token


def bucket_start(exchange_ms: int) -> datetime:
    instant = datetime.fromtimestamp(exchange_ms / 1000, tz=IST)
    minute = (instant.minute // BUCKET_MINUTES) * BUCKET_MINUTES
    return instant.replace(minute=minute, second=0, microsecond=0)


def in_cash_window(start: datetime, session_date: date) -> bool:
    if start.date() != session_date:
        return False
    open_ = start.replace(hour=9, minute=15, second=0, microsecond=0)
    close = start.replace(hour=15, minute=30, second=0, microsecond=0)
    return open_ <= start < close


class CandleBook:
    """One forming candle per index. The clock is the exchange timestamp."""

    def __init__(self, session_date: date | None = SESSION_DATE):
        self.session_date = session_date
        self.skipped = 0
        self.ticks = 0
        self._candles: dict[tuple[str, datetime], Candle] = {}
        self.last_price: dict[str, Decimal] = {}

    def add(self, instrument_key: str, exchange_ms: int | None, price) -> bool:
        if instrument_key not in _BY_KEY:
            return False
        if exchange_ms is None:
            self.skipped += 1
            return False
        try:
            number = as_decimal(price)
            start = bucket_start(int(exchange_ms))
        except (ValueError, TypeError, OSError, OverflowError):
            self.skipped += 1
            return False
        if self.session_date is not None and not in_cash_window(start, self.session_date):
            self.skipped += 1
            return False
        key = (instrument_key, start)
        current = self._candles.get(key)
        if current is None:
            self._candles[key] = Candle(start, number, number, number, number, 1)
        else:
            current.high = max(current.high, number)
            current.low = min(current.low, number)
            current.close = number
            current.ticks += 1
        self.last_price[instrument_key] = number
        self.ticks += 1
        return True

    def candles(self, instrument_key: str) -> list[Candle]:
        rows = [row for (key, _start), row in self._candles.items() if key == instrument_key]
        rows.sort(key=lambda row: row.start)
        return rows


def chart_point(candle: Candle) -> dict:
    return {
        "time": int(candle.start.timestamp()),
        "open": float(price_token(candle.open)),
        "high": float(price_token(candle.high)),
        "low": float(price_token(candle.low)),
        "close": float(price_token(candle.close)),
    }


def live_state(book: CandleBook, feed: str, quality: str, prices: dict[str, str] | None = None) -> dict:
    """Websocket session only. DEGRADED is the REST quote used when this socket is down."""
    if quality == "LIVE_VERIFIED":
        raise ValueError("source_quality cannot be the verified state")
    if feed not in {"disconnected", "connecting", "live"}:
        raise ValueError("feed status is not one of the page states")
    if feed == "live":
        if quality != "DATA_AVAILABLE":
            raise ValueError("a delivering socket is DATA_AVAILABLE")
    elif quality != "STALE":
        raise ValueError("a quiet socket is STALE")
    shown = prices or {}
    indexes = {}
    for name, key in INDEXES:
        indexes[name] = {
            "instrument_key": key,
            "price": shown.get(key, ""),
            "candles": [chart_point(candle) for candle in book.candles(key)],
        }
    return {
        "session_date": SESSION_DATE.isoformat(),
        "source": "UPSTOX WEBSOCKET",
        "feed": feed,
        "source_quality": quality,
        "entry_eligible": False,
        "policy": "ENTRY_POLICY_DISABLED",
        "indexes": indexes,
    }


def waiting_state() -> dict:
    return live_state(CandleBook(session_date=SESSION_DATE), "disconnected", "STALE")


def seed_book(book: CandleBook, state: dict) -> dict[str, str]:
    """Restore Tuesday candles after a restart. Another session is ignored."""
    if state.get("session_date") != SESSION_DATE.isoformat() or state.get("source") != "UPSTOX WEBSOCKET":
        return {}
    prices: dict[str, str] = {}
    for name, key in INDEXES:
        row = (state.get("indexes") or {}).get(name) or {}
        for candle in row.get("candles") or []:
            start_ms = int(candle["time"]) * 1000
            for offset, field in ((0, "open"), (1000, "high"), (2000, "low"), (3000, "close")):
                book.add(key, start_ms + offset, candle[field])
        if row.get("price"):
            prices[key] = str(row["price"])
    return prices


def state_json(state: dict) -> str:
    payload = json.dumps(state, separators=(",", ":"), sort_keys=True)
    if "LIVE_VERIFIED" in payload or "wss://" in payload or "Bearer" in payload:
        raise ValueError("live document refused")
    return payload


def is_full_cash_session(candles: list[Candle]) -> bool:
    if len(candles) < 2:
        return False
    first = candles[0].start
    last = candles[-1].start
    if first.date() != last.date():
        return False
    open_ = first.replace(hour=9, minute=15, second=0, microsecond=0)
    close = first.replace(hour=15, minute=27, second=0, microsecond=0)
    return first == open_ and last >= close


def summarize_book(book: CandleBook) -> dict:
    """Counts and the first and last candle only. Not a page payload."""
    indexes = {}
    for name, key in INDEXES:
        rows = book.candles(key)
        if rows:
            first, last = rows[0], rows[-1]
            indexes[name] = {
                "candle_count": len(rows),
                "tick_count": sum(row.ticks for row in rows),
                "first_ist": first.start.isoformat(),
                "last_ist": last.start.isoformat(),
                "first_ohlc": [price_token(first.open), price_token(first.high), price_token(first.low), price_token(first.close)],
                "last_ohlc": [price_token(last.open), price_token(last.high), price_token(last.low), price_token(last.close)],
                "full_session": is_full_cash_session(rows),
            }
        else:
            indexes[name] = {
                "candle_count": 0,
                "tick_count": 0,
                "first_ist": "",
                "last_ist": "",
                "first_ohlc": [],
                "last_ohlc": [],
                "full_session": False,
            }
    return {"skipped": book.skipped, "ticks": book.ticks, "indexes": indexes}


def book_from_observations(path: str) -> CandleBook:
    """Read a recorded jsonl. Does not open a socket and does not write a page."""
    book = CandleBook(session_date=None)
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line, parse_float=str, parse_int=str)
            if row.get("kind") != "ltpc":
                continue
            exchange = row.get("exchange_timestamp_ms")
            exchange_ms = int(exchange) if isinstance(exchange, str) and exchange.isdigit() else None
            book.add(row.get("instrument_key"), exchange_ms, row.get("ltp"))
    return book
