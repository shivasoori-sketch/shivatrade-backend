"""Backfill THESIS capture JSONL from VPS kaaldrishti-direct SQLite (last closed session)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class KdQuoteBackfillConfig:
    db_path: Path
    trade_date: str
    symbol: str
    thesis_symbol: str
    window_start: str
    window_end: str
    broker: str = "zerodha"
    session_id: str | None = None


def _parse_ts(exchange_ts: str | None, captured_ts: float | None) -> float:
    if exchange_ts:
        try:
            return datetime.fromisoformat(exchange_ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return float(captured_ts or 0.0)


def iter_kd_quote_captures(config: KdQuoteBackfillConfig) -> Iterator[dict]:
    """Yield CaptureSession-compatible rows from kd quotes + observations."""
    session_id = config.session_id or config.trade_date
    con = sqlite3.connect(config.db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT q.ltp, q.oi, q.volume, q.bid, q.ask, q.bid_qty, q.ask_qty, q.exchange_ts,
               o.captured_ts
        FROM quotes q
        JOIN observations o ON q.obs_id = o.id
        WHERE q.symbol = ? AND o.trade_date = ?
          AND q.exchange_ts >= ? AND q.exchange_ts <= ?
        ORDER BY o.captured_ts
        """,
        (config.symbol, config.trade_date, config.window_start, config.window_end),
    )
    prev_vol: float | None = None
    for r in rows:
        vol = r["volume"]
        ltq = 0
        if vol is not None and prev_vol is not None:
            ltq = max(0, int(vol - prev_vol))
        if vol is not None:
            prev_vol = float(vol)
        depth: dict[str, list[dict[str, float]]] = {"buy": [], "sell": []}
        if r["bid"] and r["bid_qty"]:
            depth["buy"].append({"price": float(r["bid"]), "quantity": float(r["bid_qty"])})
        if r["ask"] and r["ask_qty"]:
            depth["sell"].append({"price": float(r["ask"]), "quantity": float(r["ask_qty"])})
        raw = {
            "last_price": r["ltp"],
            "last_traded_quantity": ltq,
            "volume_traded": int(vol or 0),
            "oi": int(r["oi"] or 0),
            "total_buy_quantity": int(r["bid_qty"] or 0),
            "total_sell_quantity": int(r["ask_qty"] or 0),
            "exchange_timestamp": r["exchange_ts"],
            "depth": depth,
            "_source": "vps_kd_quote_backfill",
            "_provenance": "kaaldrishti.sqlite3 quotes+observations",
        }
        yield {
            "symbol": config.thesis_symbol,
            "broker": config.broker,
            "session_id": session_id,
            "mode": "quote_backfill",
            "ts": _parse_ts(r["exchange_ts"], r["captured_ts"]),
            "raw": raw,
        }
    con.close()


def write_capture_jsonl(path: Path, rows: Iterator[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
            count += 1
    return count
