"""Validate replayed capture sessions: §2.2 field coverage + 1m candle export."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from thesis.candle_builder import CandleBuilder, minute_start_epoch
from thesis.ingestor.capture import CaptureSession
from thesis.ingestor.feed import FeedIngestor
from thesis.ingestor.normalize import normalize_broker_tick
from thesis.ingestor.redis_store import InMemoryRedisStore, ThesisRedisStore
from thesis.types import TickInput


@dataclass(frozen=True)
class FieldAudit:
    lines: int
    populated: dict[str, int]
    ltq_zero: int

    @property
    def ltp_pct(self) -> float:
        return 100.0 * self.populated.get("ltp", 0) / max(self.lines, 1)


def audit_capture_file(path: Path) -> FieldAudit:
    populated: Counter[str] = Counter()
    ltq_zero = 0
    rows = CaptureSession.load_records(path)
    for row in rows:
        raw = row.get("raw") or {}
        tick = normalize_broker_tick(raw, symbol=str(row.get("symbol", "")), timestamp=row.get("ts"))
        if tick.ltp > 0:
            populated["ltp"] += 1
        if tick.ltq >= 0:
            populated["ltq"] += 1
            if tick.ltq == 0:
                ltq_zero += 1
        if tick.vtt > 0:
            populated["vtt"] += 1
        if tick.oi > 0:
            populated["oi"] += 1
        if tick.tbq > 0 or tick.tsq > 0:
            populated["tbq_tsq"] += 1
        if tick.depth_bid or tick.depth_ask:
            populated["depth"] += 1
    return FieldAudit(lines=len(rows), populated=dict(populated), ltq_zero=ltq_zero)


def expected_minute_candles(ticks: list[TickInput]) -> dict[int, dict[str, float]]:
    """Reference OHLCV aggregation independent of CandleBuilder."""
    buckets: dict[int, list[TickInput]] = {}
    for t in ticks:
        m = minute_start_epoch(t.timestamp)
        buckets.setdefault(m, []).append(t)
    out: dict[int, dict[str, float]] = {}
    for m, group in buckets.items():
        ltps = [x.ltp for x in group]
        vol = sum(max(0, x.ltq) for x in group)
        out[m] = {
            "open": ltps[0],
            "high": max(ltps),
            "low": min(ltps),
            "close": ltps[-1],
            "volume": float(vol),
        }
    return out


def replay_and_build(path: Path) -> tuple[list[tuple[str, object]], list[TickInput]]:
    redis = InMemoryRedisStore()
    store = ThesisRedisStore(redis)
    closed: list[tuple[str, object]] = []

    def _on_close(sym: str, candle: object) -> None:
        closed.append((sym, candle))

    builder = CandleBuilder(store, on_candle_closed=_on_close)
    ingestor = FeedIngestor(
        store=store,
        build_candles=True,
        candle_builder=builder,
        on_candle_closed=_on_close,
    )
    ticks: list[TickInput] = []
    for row in CaptureSession.load_records(path):
        sym = str(row["symbol"])
        raw = dict(row["raw"])
        ts = float(row["ts"]) if row.get("ts") is not None else None
        tick = ingestor.on_raw_tick(sym, raw, timestamp=ts)
        ticks.append(tick)
    return closed, ticks


def compare_candles(
    built_closed: list[tuple[str, object]],
    ticks: list[TickInput],
) -> tuple[int, int]:
    expected = expected_minute_candles(ticks)
    matched = 0
    mismatches = 0
    for _sym, candle in built_closed:
        exp = expected.get(candle.minute_start)
        if not exp:
            mismatches += 1
            continue
        ok = (
            candle.ohlc.open == exp["open"]
            and candle.ohlc.high == exp["high"]
            and candle.ohlc.low == exp["low"]
            and candle.ohlc.close == exp["close"]
            and float(candle.volume) == exp["volume"]
        )
        if ok:
            matched += 1
        else:
            mismatches += 1
    return matched, mismatches


def export_candle_csv(path: Path, built_closed: list[tuple[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "symbol",
                "minute_start_utc",
                "open",
                "high",
                "low",
                "close",
                "volume_ltq_sum",
                "source",
            ]
        )
        for sym, candle in sorted(built_closed, key=lambda x: x[1].minute_start):
            w.writerow(
                [
                    sym,
                    candle.minute_start,
                    candle.ohlc.open,
                    candle.ohlc.high,
                    candle.ohlc.low,
                    candle.ohlc.close,
                    candle.volume,
                    "thesis_candle_builder",
                ]
            )
