"""Load Kite historical_data baselines and compare to THESIS candle builder output."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from thesis.candle_builder import ClosedCandle1m

IST = timezone(timedelta(hours=5, minutes=30))

DEFAULT_KITE_FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "kite"
    / "nfo_nifty26novfut_2026-11-09_0915_1030_ist.json"
)

DEFAULT_REPLAY_FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "replay"
    / "vps_nifty_fut_2026-11-09_slice.jsonl"
)


@dataclass(frozen=True)
class KiteMinuteCandle:
    minute_start: int
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass(frozen=True)
class CandleDiff:
    minute_start: int
    field: str
    expected: float | int
    actual: float | int


def _parse_kite_date(value: str) -> int:
    """Parse Kite historical row date to UTC epoch minute start."""
    text = value.strip()
    for fmt in (
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S+0530",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            if fmt.endswith("%z") or fmt.endswith("+0530"):
                dt = datetime.strptime(text.replace("+05:30", "+0530"), fmt)
            else:
                dt = datetime.strptime(text, fmt).replace(tzinfo=IST)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=IST)
            return int(dt.astimezone(timezone.utc).timestamp() // 60 * 60)
        except ValueError:
            continue
    raise ValueError(f"Unparseable Kite date: {value!r}")


def load_kite_fixture(path: Path | None = None) -> tuple[dict[str, Any], list[KiteMinuteCandle]]:
    path = path or DEFAULT_KITE_FIXTURE
    raw = json.loads(path.read_text(encoding="utf-8"))
    candles: list[KiteMinuteCandle] = []
    for row in raw.get("candles") or []:
        minute_start = _parse_kite_date(str(row["date"]))
        candles.append(
            KiteMinuteCandle(
                minute_start=minute_start,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
            )
        )
    candles.sort(key=lambda c: c.minute_start)
    return raw, candles


def dedupe_builder_candles(
    closed: list[tuple[str, ClosedCandle1m]],
) -> list[ClosedCandle1m]:
    """FeedIngestor + CandleBuilder can emit duplicate closes; keep the last per minute."""
    by_minute: dict[int, ClosedCandle1m] = {}
    for _sym, candle in closed:
        by_minute[candle.minute_start] = candle
    return [by_minute[k] for k in sorted(by_minute)]


def fetch_kite_historical_live(
    *,
    instrument_token: int,
    from_date: str,
    to_date: str,
    interval: str = "minute",
) -> list[dict[str, Any]]:
    """Call Kite historical_data when credentials exist (local/VPS only; not required in CI)."""
    from kiteconnect import KiteConnect

    from thesis.ingestor.kite_bind import load_kite_bind

    api_key = os.environ.get("KITE_API_KEY", "").strip()
    access_token = os.environ.get("KITE_ACCESS_TOKEN", "").strip()
    if not api_key or not access_token:
        bind = load_kite_bind()
        if not bind.ok:
            raise RuntimeError(f"Kite bind unavailable: {bind.reason}")
        api_key, access_token = bind.api_key, bind.access_token

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    return list(
        kite.historical_data(
            instrument_token,
            from_date,
            to_date,
            interval=interval,
            continuous=False,
            oi=False,
        )
    )


def compare_builder_to_kite(
    built: list[ClosedCandle1m],
    kite: list[KiteMinuteCandle],
    *,
    volume_tolerance: int = 1,
) -> tuple[list[CandleDiff], dict[str, Any]]:
    diffs: list[CandleDiff] = []
    built_map = {c.minute_start: c for c in built}
    kite_map = {c.minute_start: c for c in kite}

    if len(built_map) != len(kite_map):
        diffs.append(
            CandleDiff(
                minute_start=-1,
                field="candle_count",
                expected=len(kite_map),
                actual=len(built_map),
            )
        )

    for minute_start, kc in sorted(kite_map.items()):
        bc = built_map.get(minute_start)
        if bc is None:
            diffs.append(CandleDiff(minute_start, "missing_builder", 1, 0))
            continue
        for field in ("open", "high", "low", "close"):
            exp = getattr(kc, field)
            act = getattr(bc.ohlc, field)
            if exp != act:
                diffs.append(CandleDiff(minute_start, field, exp, act))
        if abs(int(bc.volume) - kc.volume) > volume_tolerance:
            diffs.append(CandleDiff(minute_start, "volume", kc.volume, int(bc.volume)))

    extra = sorted(set(built_map) - set(kite_map))
    for minute_start in extra:
        diffs.append(CandleDiff(minute_start, "extra_builder", 0, 1))

    report = {
        "kite_candles": len(kite_map),
        "builder_candles": len(built_map),
        "diff_count": len(diffs),
        "diffs": [
            {
                "minute_start": d.minute_start,
                "field": d.field,
                "expected": d.expected,
                "actual": d.actual,
            }
            for d in diffs
        ],
        "pass": len(diffs) == 0,
    }
    return diffs, report


def write_reconciliation_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
