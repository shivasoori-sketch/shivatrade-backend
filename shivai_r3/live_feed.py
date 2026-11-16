"""Tuesday cash-session feeder. It exits outside that window and does not serve the page.

The subscribe frame is the binary one that already produced prices.
This process never writes brokers.json and never places an order.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from shivai_r3.candles import (
    SESSION_DATE,
    CandleBook,
    IST,
    live_state,
    price_token,
    seed_book,
    state_json,
)
from shivai_r3.fc01_capture import (
    KEYS,
    TOKEN_FILE,
    authorize,
    decode_frame,
    load_decoder,
    observations_from_decoded,
    subscribe_frame,
)

OPEN = datetime(2026, 11, 17, 9, 15, tzinfo=IST)
CLOSE = datetime(2026, 11, 17, 15, 30, tzinfo=IST)
LIVE_PATH = Path(os.environ.get("SHIVAI_LIVE", "/opt/shivtrade/shivai/live.json"))


def phase(now: datetime) -> str:
    local = now.astimezone(IST)
    if local.date() != SESSION_DATE:
        return "exit"
    if local >= CLOSE:
        return "exit"
    if local < OPEN - timedelta(minutes=2):
        return "exit"
    if local < OPEN:
        return "wait"
    return "run"


def publish(state: dict, path: Path) -> None:
    payload = state_json(state)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)


async def _session(path: Path) -> int:
    book = CandleBook(session_date=SESSION_DATE)
    prices: dict[str, str] = {}
    if path.is_file():
        try:
            prices = seed_book(book, json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):
            prices = {}
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        publish(live_state(book, "disconnected", "STALE", prices), path)
        print("authorize_status missing", file=sys.stderr)
        return 0
    decoder = load_decoder()
    last_tick: datetime | None = None
    while phase(datetime.now(IST)) == "run":
        status, uri = authorize(token)
        if status != 200 or not uri:
            publish(live_state(book, "disconnected", "STALE", prices), path)
            print(f"authorize_status {status}", file=sys.stderr)
            await asyncio.sleep(5)
            continue
        publish(live_state(book, "connecting", "STALE", prices), path)
        try:
            import websockets

            async with websockets.connect(
                uri,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_size=8 * 1024 * 1024,
            ) as ws:
                await ws.send(subscribe_frame(KEYS))
                wrote = 0.0
                while phase(datetime.now(IST)) == "run":
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    except TimeoutError:
                        quiet = last_tick is None or (datetime.now(IST) - last_tick).total_seconds() > 15
                        quality = "STALE" if quiet else "DEGRADED"
                        feed = "disconnected" if quiet else "live"
                        publish(live_state(book, feed, quality, prices), path)
                        continue
                    received = datetime.now(IST).isoformat()
                    try:
                        decoded = decode_frame(raw, decoder)
                    except Exception as exc:
                        print(f"decode_error {type(exc).__name__}", file=sys.stderr)
                        continue
                    changed = False
                    for row in observations_from_decoded(decoded, received):
                        if row.get("kind") != "ltpc":
                            continue
                        key = row.get("instrument_key")
                        if not book.add(key, row.get("exchange_timestamp_ms"), row.get("ltp")):
                            continue
                        prices[key] = price_token(book.last_price[key])
                        changed = True
                        last_tick = datetime.now(IST)
                    if not changed:
                        continue
                    now = time.monotonic()
                    if now - wrote >= 1:
                        publish(live_state(book, "live", "DEGRADED", prices), path)
                        wrote = now
        except Exception as exc:
            print(f"feed_error {type(exc).__name__}", file=sys.stderr)
            publish(live_state(book, "disconnected", "STALE", prices), path)
            await asyncio.sleep(2)
    publish(live_state(book, "disconnected", "STALE", prices), path)
    return 0


def main() -> int:
    action = phase(datetime.now(IST))
    if action == "exit":
        print("outside the Tuesday session")
        return 0
    if action == "wait":
        time.sleep(max(0, (OPEN - datetime.now(IST)).total_seconds()))
    return asyncio.run(_session(LIVE_PATH))


if __name__ == "__main__":
    raise SystemExit(main())
