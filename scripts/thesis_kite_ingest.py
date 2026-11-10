#!/usr/bin/env python3
"""THESIS Step 2 — KiteTicker full-mode ingest (systemd entry)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from thesis.ingestor.capture import replay_capture  # noqa: E402
from thesis.ingestor.feed import FeedIngestor  # noqa: E402
from thesis.ingestor.forwarder import forwarder_from_env, wait_for_api  # noqa: E402
from thesis.ingestor.kite_live import build_live_ingest, run_live_main  # noqa: E402
from thesis.ingestor.kite_bind import load_kite_bind  # noqa: E402
from thesis.ingestor.metrics import metrics_from_jsonl, print_metrics_json  # noqa: E402
from thesis.ingestor.redis_store import InMemoryRedisStore, ThesisRedisStore  # noqa: E402


def _replay(path: Path, *, forward: bool) -> int:
    logging.basicConfig(level=logging.INFO)
    store = ThesisRedisStore(InMemoryRedisStore())
    ingestor = FeedIngestor(store=store, build_candles=True)
    fwd = forwarder_from_env() if forward else None
    if forward:
        if not wait_for_api(fwd.base_url):
            logging.error("API not up for replay forward")
            return 2
    count = 0
    for row in __import__(
        "thesis.ingestor.capture", fromlist=["CaptureSession"]
    ).CaptureSession.load_records(path):
        ts = row.get("ts")
        sym = str(row["symbol"])
        raw = dict(row["raw"])
        ingestor.on_raw_tick(sym, raw, timestamp=float(ts) if ts else None)
        if fwd:
            fwd.forward_tick(sym, raw, timestamp=float(ts) if ts else None)
        count += 1
    if fwd:
        fwd.close()
    logging.info("replayed %s lines from %s metrics=%s", count, path, metrics_from_jsonl(path))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="THESIS Kite full-mode ingest")
    parser.add_argument(
        "mode",
        choices=("live", "replay", "metrics"),
        help="live=KiteTicker; replay=JSONL dry-run; metrics=audit file",
    )
    parser.add_argument("--path", type=Path, help="JSONL path for replay/metrics")
    parser.add_argument(
        "--no-forward",
        action="store_true",
        help="Capture/replay only; do not POST to thesis API",
    )
    args = parser.parse_args()

    if args.mode == "metrics":
        if not args.path:
            parser.error("--path required for metrics")
        print_metrics_json(args.path)
        return 0

    if args.mode == "replay":
        if not args.path or not args.path.is_file():
            parser.error("--path to existing JSONL required for replay")
        return _replay(args.path, forward=not args.no_forward)

    bind = load_kite_bind()
    if not bind.ok:
        logging.basicConfig(level=logging.ERROR)
        logging.error("Kite session not ready: %s", bind.reason)
        return 2
    return run_live_main()


if __name__ == "__main__":
    raise SystemExit(main())
