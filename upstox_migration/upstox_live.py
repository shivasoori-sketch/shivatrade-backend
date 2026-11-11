#!/usr/bin/env python3
"""Shadow PulseGuard tick cache — Upstox WS → latest_tick_cache.json."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upstox_adapters import UPSTOX_TO_QUOTE_KEY, adapt_live_cache_row  # noqa: E402
from upstox_client import UpstoxMarketWebSocket, UpstoxRestClient, ist_now, write_json_atomic  # noqa: E402

MIGRATION_ROOT = Path("/opt/shivtrade/upstox_migration")
CACHE_PATH = MIGRATION_ROOT / "state" / "latest_tick_cache.json"
HEALTH_PATH = MIGRATION_ROOT / "state" / "live_health.json"
DEFAULT_KEYS = list(UPSTOX_TO_QUOTE_KEY.keys())
logger = logging.getLogger(__name__)


class LiveTickCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._quotes: dict[str, dict] = {}

    def update_batch(self, batch: dict[str, dict]) -> None:
        with self._lock:
            for instrument_key, tick in batch.items():
                row = adapt_live_cache_row(instrument_key, tick)
                key = f"{row['exchange']}:{row['tradingsymbol']}".upper()
                self._quotes[key] = row

    def snapshot(self) -> dict[str, dict]:
        with self._lock:
            return dict(self._quotes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upstox shadow live tick cache")
    parser.add_argument("--max-runtime-sec", type=int, default=0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    rest = UpstoxRestClient()
    keys = DEFAULT_KEYS
    try:
        fut = rest.resolve_nearest_future("NSE_INDEX|Nifty 50")
        if fut.get("instrument_key"):
            keys = list(dict.fromkeys(keys + [str(fut["instrument_key"])]))
    except Exception as exc:  # noqa: BLE001
        logger.warning("nifty_fut_optional %s", exc)

    cache = LiveTickCache()
    stop = False

    def _sig(*_: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    ws = UpstoxMarketWebSocket(instrument_keys=keys, mode="full", on_ticks=cache.update_batch, rest=rest)
    started = time.monotonic()

    def persist_loop() -> None:
        while not stop:
            write_json_atomic(CACHE_PATH, cache.snapshot())
            write_json_atomic(
                HEALTH_PATH,
                {
                    "schema": "upstox_live_health_v1",
                    "updated_at": ist_now().isoformat(),
                    "cache_path": str(CACHE_PATH),
                    "quote_count": len(cache.snapshot()),
                    "ws": ws.health.__dict__,
                },
            )
            time.sleep(1)

    threading.Thread(target=ws.run_forever, name="upstox-live-ws", daemon=True).start()
    threading.Thread(target=persist_loop, name="upstox-live-persist", daemon=True).start()

    while not stop:
        if args.max_runtime_sec and (time.monotonic() - started) >= args.max_runtime_sec:
            break
        time.sleep(0.5)
    ws.stop()
    write_json_atomic(CACHE_PATH, cache.snapshot())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
