"""Independent KiteTicker density probe — separate WS object from thesis-ingest."""

from __future__ import annotations

import json
import logging
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from thesis.ingestor.kite_bind import load_kite_bind
from thesis.ingestor.kite_symbols import resolve_requested_symbols

logger = logging.getLogger(__name__)


@dataclass
class DensityProbeStats:
    tick_count: int = 0
    batch_count: int = 0
    window_start: float = field(default_factory=time.time)
    window_ticks: int = 0
    per_symbol: dict[str, int] = field(default_factory=dict)
    connection_id: str = ""
    subscribed_tokens: list[int] = field(default_factory=list)
    mode_set: str = "full"
    stop: threading.Event = field(default_factory=threading.Event)

    def note_batch(self, ticks: list[dict], token_to_symbol: dict[int, str]) -> None:
        self.batch_count += 1
        for raw in ticks:
            tok = int(raw.get("instrument_token") or 0)
            sym = token_to_symbol.get(tok, f"token:{tok}")
            self.tick_count += 1
            self.window_ticks += 1
            self.per_symbol[sym] = self.per_symbol.get(sym, 0) + 1

    def snapshot(self, *, reset_window: bool = True) -> dict[str, Any]:
        elapsed = max(0.001, time.time() - self.window_start)
        out = {
            "probe": "thesis_kite_density_probe",
            "connection_id": self.connection_id,
            "ticks_total": self.tick_count,
            "batches_total": self.batch_count,
            "ticks_per_sec_window": round(self.window_ticks / elapsed, 4),
            "window_sec": round(elapsed, 2),
            "per_symbol": dict(sorted(self.per_symbol.items())),
            "subscribed_tokens": self.subscribed_tokens,
            "mode": self.mode_set,
        }
        if reset_window:
            self.window_start = time.time()
            self.window_ticks = 0
        return out

    def log_line(self) -> str:
        s = self.snapshot(reset_window=True)
        return "THESIS_DENSITY_PROBE " + " ".join(
            f"{k}={v}" if not isinstance(v, dict) else f"{k}={json.dumps(v, sort_keys=True)}"
            for k, v in s.items()
        )


def run_density_probe(
    *,
    duration_sec: float = 120.0,
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    """Connect a dedicated KiteTicker, subscribe full mode, count ticks for duration_sec."""
    from kiteconnect import KiteConnect, KiteTicker

    bind = load_kite_bind()
    if not bind.ok:
        raise RuntimeError(f"Kite bind failed: {bind.reason}")

    kite = KiteConnect(api_key=bind.api_key)
    kite.set_access_token(bind.access_token)
    sym_list = symbols or [
        s.strip()
        for s in (
            __import__("os").environ.get(
                "THESIS_PROBE_SYMBOLS",
                "NSE:NIFTY26NOVFUT,NSE:SBIN",
            )
        ).split(",")
        if s.strip()
    ]
    instruments = resolve_requested_symbols(kite, sym_list)
    if not instruments:
        raise RuntimeError("No instruments resolved for density probe")

    token_to_symbol = {i.token: i.thesis_symbol for i in instruments}
    tokens = list(token_to_symbol.keys())
    stats = DensityProbeStats(connection_id=f"probe-{int(time.time())}")

    ticker = KiteTicker(bind.api_key, bind.access_token)

    def on_ticks(_ws: Any, ticks: list[dict]) -> None:
        stats.note_batch(ticks, token_to_symbol)

    def on_connect(_ws: Any, _response: Any) -> None:
        logger.info(
            "probe connected; subscribing %s tokens (bind=%s)",
            len(tokens),
            bind.redacted,
        )
        ticker.subscribe(tokens)
        ticker.set_mode(ticker.MODE_FULL, tokens)
        stats.subscribed_tokens = tokens

    ticker.on_ticks = on_ticks
    ticker.on_connect = on_connect
    ticker.connect(threaded=True)

    def _shutdown(*_args: object) -> None:
        stats.stop.set()
        try:
            ticker.close()
        except Exception:
            pass

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    interval = float(__import__("os").environ.get("THESIS_PROBE_LOG_INTERVAL_SEC", "15"))
    end = time.time() + duration_sec
    while time.time() < end and not stats.stop.is_set():
        time.sleep(interval)
        logger.info("%s", stats.log_line())

    _shutdown()
    final = stats.snapshot(reset_window=False)
    final["duration_requested_sec"] = duration_sec
    final["bind_reason"] = bind.redacted
    return final


def run_density_probe_main() -> int:
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Independent KiteTicker density probe")
    parser.add_argument(
        "--duration",
        type=float,
        default=float(os.environ.get("THESIS_PROBE_DURATION_SEC", "120")),
        help="Seconds to run before exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print final stats as JSON on stdout",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        result = run_density_probe(duration_sec=args.duration)
    except Exception as exc:
        logger.error("probe failed: %s", exc)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    logger.info("probe done ticks_total=%s tps=%s", result["ticks_total"], result["ticks_per_sec_window"])
    return 0
