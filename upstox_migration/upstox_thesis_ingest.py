#!/usr/bin/env python3
"""Shadow THESIS ingest — Upstox Market Data Feed V3 (full mode)."""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upstox_adapters import thesis_jsonl_row  # noqa: E402
from upstox_client import UpstoxMarketWebSocket, UpstoxRestClient, ist_now, write_json_atomic  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
MIGRATION_ROOT = Path("/opt/shivtrade/upstox_migration")
SESSIONS = MIGRATION_ROOT / "sessions"
HEALTH_PATH = MIGRATION_ROOT / "state" / "thesis_ingest_health.json"
DEFAULT_OUT = SESSIONS / "test-2026-11-11.jsonl"
logger = logging.getLogger(__name__)


def resolve_nifty_fut_key(rest: UpstoxRestClient) -> str:
    fut = rest.resolve_nearest_future("NSE_INDEX|Nifty 50")
    key = fut.get("instrument_key")
    if not key:
        raise RuntimeError("NIFTY FUT instrument_key missing from contract API")
    return str(key)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upstox shadow THESIS ingest")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUT,
        help="JSONL output path",
    )
    parser.add_argument(
        "--max-runtime-sec",
        type=int,
        default=0,
        help="0 = run until SIGTERM; else stop after N seconds",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    rest = UpstoxRestClient()
    fut_key = resolve_nifty_fut_key(rest)
    keys = [fut_key, "NSE_INDEX|Nifty 50"]
    logger.info("subscribing thesis ingest keys=%s", keys)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    session_id = datetime.now(IST).strftime("%Y%m%d")
    started = time.monotonic()
    lines = 0
    stop = False

    def _sig(*_: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    def on_ticks(batch: dict) -> None:
        nonlocal lines
        with args.output.open("a", encoding="utf-8") as fh:
            for instrument_key, tick in batch.items():
                row = thesis_jsonl_row(instrument_key, tick, session_id=session_id)
                fh.write(json.dumps(row, separators=(",", ":"), default=str) + "\n")
                lines += 1
            fh.flush()

    ws = UpstoxMarketWebSocket(instrument_keys=keys, mode="full", on_ticks=on_ticks, rest=rest)

    def _health_loop() -> None:
        while not stop:
            write_json_atomic(
                HEALTH_PATH,
                {
                    "schema": "upstox_thesis_ingest_health_v1",
                    "updated_at": ist_now().isoformat(),
                    "output": str(args.output),
                    "lines": lines,
                    "nifty_fut_key": fut_key,
                    "ws": ws.health.__dict__,
                },
            )
            time.sleep(5)

    import threading

    threading.Thread(target=ws.run_forever, name="upstox-thesis-ws", daemon=True).start()
    threading.Thread(target=_health_loop, name="upstox-thesis-health", daemon=True).start()

    while not stop:
        if args.max_runtime_sec and (time.monotonic() - started) >= args.max_runtime_sec:
            break
        time.sleep(0.5)
    ws.stop()
    logger.info("thesis_ingest_stop lines=%s path=%s", lines, args.output)
    return 0 if lines > 0 or args.max_runtime_sec == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
