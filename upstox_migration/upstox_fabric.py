#!/usr/bin/env python3
"""Shadow capture fabric — Upstox WS ticks → 30s stream buckets for PGE."""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upstox_adapters import fabric_bucket_row  # noqa: E402
from upstox_client import UpstoxMarketWebSocket, UpstoxRestClient, ist_now, write_json_atomic  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")
MIGRATION_ROOT = Path("/opt/shivtrade/upstox_migration")
BUCKET_DIR = MIGRATION_ROOT / "state" / "fabric_buckets"
INDEX_KEYS = [
    "NSE_INDEX|Nifty 50",
    "NSE_INDEX|Nifty Bank",
    "BSE_INDEX|SENSEX",
]
HEALTH_PATH = MIGRATION_ROOT / "state" / "fabric_health.json"
logger = logging.getLogger(__name__)


@dataclass
class HalfAcc:
    open: float
    high: float
    low: float
    close: float
    ticks: int = 1

    def add(self, price: float) -> None:
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.ticks += 1


class FabricAggregator:
    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.buckets: dict[tuple[str, str], HalfAcc] = {}
        self.written = 0

    def _bucket_start(self, ts: datetime) -> datetime:
        ts = ts.astimezone(IST).replace(microsecond=0)
        return ts.replace(second=0 if ts.second < 30 else 30)

    def on_ticks(self, batch: dict[str, dict]) -> None:
        with self._lock:
            for instrument_key, tick in batch.items():
                ltp = tick.get("ltp")
                if ltp is None:
                    continue
                price = float(ltp)
                if price <= 0:
                    continue
                ts = tick.get("timestamp")
                if not isinstance(ts, datetime):
                    ts = ist_now()
                start = self._bucket_start(ts)
                key = (instrument_key, start.isoformat())
                acc = self.buckets.get(key)
                if acc:
                    acc.add(price)
                else:
                    self.buckets[key] = HalfAcc(price, price, price, price)

    def flush_closed(self, now: datetime | None = None) -> int:
        now = now or ist_now()
        closed_boundary = self._bucket_start(now)
        if now.second >= 30:
            pass
        else:
            closed_boundary = closed_boundary - timedelta(seconds=30)
        flushed = 0
        with self._lock:
            pending = [
                k
                for k in self.buckets
                if datetime.fromisoformat(k[1]).astimezone(IST) <= closed_boundary
            ]
            for instrument_key, start_iso in pending:
                acc = self.buckets.pop((instrument_key, start_iso))
                start = datetime.fromisoformat(start_iso)
                end = start + timedelta(seconds=30)
                row = fabric_bucket_row(
                    instrument_key=instrument_key,
                    bucket_start=start,
                    open_=acc.open,
                    high=acc.high,
                    low=acc.low,
                    close=acc.close,
                    tick_count=acc.ticks,
                    half_bucket_ticks=[acc.ticks],
                )
                row["end"] = end.isoformat()
                day = start.strftime("%Y%m%d")
                fname = f"{day}_{instrument_key.replace('|', '_')}_{start.strftime('%H%M%S')}.json"
                path = self.out_dir / fname
                path.write_text(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
                flushed += 1
                self.written += 1
        return flushed


def resolve_futures(rest: UpstoxRestClient) -> list[str]:
    out = list(INDEX_KEYS)
    for index_key in ("NSE_INDEX|Nifty 50", "NSE_INDEX|Nifty Bank", "BSE_INDEX|SENSEX"):
        try:
            fut = rest.resolve_nearest_future(index_key)
            ik = fut.get("instrument_key")
            if ik:
                out.append(str(ik))
        except Exception as exc:  # noqa: BLE001
            logger.warning("future_resolve_skip %s %s", index_key, exc)
    return list(dict.fromkeys(out))


def main() -> int:
    parser = argparse.ArgumentParser(description="Upstox shadow fabric buckets")
    parser.add_argument("--max-runtime-sec", type=int, default=0)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    rest = UpstoxRestClient()
    keys = resolve_futures(rest)
    logger.info("fabric subscribe count=%s", len(keys))

    agg = FabricAggregator(BUCKET_DIR)
    stop = False

    def _sig(*_: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _sig)
    signal.signal(signal.SIGINT, _sig)

    ws = UpstoxMarketWebSocket(instrument_keys=keys, mode="full", on_ticks=agg.on_ticks, rest=rest)

    started = time.monotonic()

    def flush_loop() -> None:
        while not stop:
            n = agg.flush_closed()
            if n:
                logger.info("fabric_flushed buckets=%s total=%s", n, agg.written)
            write_json_atomic(
                HEALTH_PATH,
                {
                    "schema": "upstox_fabric_health_v1",
                    "updated_at": ist_now().isoformat(),
                    "bucket_dir": str(BUCKET_DIR),
                    "buckets_written": agg.written,
                    "open_buckets": len(agg.buckets),
                    "ws": ws.health.__dict__,
                },
            )
            time.sleep(5)

    threading.Thread(target=ws.run_forever, name="upstox-fabric-ws", daemon=True).start()
    threading.Thread(target=flush_loop, name="upstox-fabric-flush", daemon=True).start()

    while not stop:
        if args.max_runtime_sec and (time.monotonic() - started) >= args.max_runtime_sec:
            break
        time.sleep(0.5)
    ws.stop()
    agg.flush_closed()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
