"""Session capture metrics: tick density, gaps, data_stale simulation."""

from __future__ import annotations

import json
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from thesis.ingestor.capture import CaptureSession


@dataclass
class LiveIngestMetrics:
    gap_threshold_seconds: float = 5.0
    tick_count: int = 0
    gap_count: int = 0
    last_tick_wall: float = field(default_factory=time.time)
    window_start: float = field(default_factory=time.time)
    window_ticks: int = 0
    per_symbol_last_ts: dict[str, float] = field(default_factory=dict)
    stale_symbols: set[str] = field(default_factory=set)

    def note_tick(self, symbol: str, ts: float) -> None:
        self.tick_count += 1
        self.window_ticks += 1
        self.last_tick_wall = time.time()
        last = self.per_symbol_last_ts.get(symbol)
        if last is not None and ts - last > self.gap_threshold_seconds:
            self.gap_count += 1
            self.stale_symbols.add(symbol)
        elif symbol in self.stale_symbols and last is not None:
            if ts - last <= self.gap_threshold_seconds:
                self.stale_symbols.discard(symbol)
        self.per_symbol_last_ts[symbol] = ts

    def snapshot_line(self) -> str:
        elapsed = max(0.001, time.time() - self.window_start)
        tps = self.window_ticks / elapsed
        stale = ",".join(sorted(self.stale_symbols)) or "none"
        line = (
            f"THESIS_INGEST_METRICS ticks_total={self.tick_count} "
            f"ticks_per_sec={tps:.2f} gaps={self.gap_count} "
            f"data_stale_symbols={stale}"
        )
        self.window_start = time.time()
        self.window_ticks = 0
        return line


def metrics_from_jsonl(
    path: Path,
    *,
    gap_threshold_seconds: float = 5.0,
) -> dict[str, Any]:
    """Offline audit of a captured session file."""
    rows = CaptureSession.load_records(path)
    by_sym: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_sym[str(row["symbol"])].append(float(row.get("ts") or 0))
    gaps = 0
    stale_events = 0
    duration = 0.0
    for _sym, ts_list in by_sym.items():
        ts_list.sort()
        if len(ts_list) >= 2:
            duration = max(duration, ts_list[-1] - ts_list[0])
        for prev, cur in zip(ts_list, ts_list[1:]):
            if cur - prev > gap_threshold_seconds:
                gaps += 1
                stale_events += 1
    lines = len(rows)
    tps = lines / max(duration, 1.0)
    modes = {str(r.get("mode", "?")) for r in rows}
    return {
        "path": str(path),
        "lines": lines,
        "duration_sec": round(duration, 2),
        "ticks_per_sec": round(tps, 3),
        "gaps_over_threshold": gaps,
        "data_stale_gap_events": stale_events,
        "modes": sorted(modes),
        "symbols": sorted(by_sym.keys()),
    }


def print_metrics_json(path: Path) -> None:
    out = metrics_from_jsonl(path)
    print(json.dumps(out, indent=2))
