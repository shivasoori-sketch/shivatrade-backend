"""F-C01 index-feed recorder. A separate process. It does not serve the SHIVAI page.

The only network calls are the Upstox V3 authorize GET and the websocket it returns.
A connection is not a pass. This tool never sets DATA_VALIDATED or SIGNAL_ELIGIBLE.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

KEYS = (
    "NSE_INDEX|Nifty 50",
    "NSE_INDEX|Nifty Bank",
    "BSE_INDEX|SENSEX",
)
AUTHORIZE_URL = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
TOKEN_FILE = Path("/opt/shivtrade/shared/state/upstox_token.txt")
PB2_DIR = Path("/opt/shivtrade/upstox_migration")
IST = ZoneInfo("Asia/Kolkata")
GAP_MS = 5000
CASH_OPEN = (9, 15)
CASH_CLOSE = (15, 30)


@dataclass
class IndexCapture:
    subscription_ack: bool = False
    count: int = 0
    first_exchange_timestamp_ms: int | None = None
    last_exchange_timestamp_ms: int | None = None
    first_received_at_utc: str | None = None
    last_received_at_utc: str | None = None
    exchange_timestamp_present: int = 0
    exchange_timestamp_absent: int = 0
    gaps: list[dict] = field(default_factory=list)
    duplicate_count: int = 0
    out_of_order_count: int = 0
    _seen_exchange_ms: set[int] = field(default_factory=set)

    def note(self, exchange_ms: int | None, received_at_utc: str) -> None:
        self.count += 1
        if self.first_received_at_utc is None:
            self.first_received_at_utc = received_at_utc
        self.last_received_at_utc = received_at_utc
        if exchange_ms is None:
            self.exchange_timestamp_absent += 1
            return
        self.exchange_timestamp_present += 1
        if exchange_ms in self._seen_exchange_ms:
            self.duplicate_count += 1
        self._seen_exchange_ms.add(exchange_ms)
        if self.first_exchange_timestamp_ms is None:
            self.first_exchange_timestamp_ms = exchange_ms
        if self.last_exchange_timestamp_ms is None or exchange_ms >= self.last_exchange_timestamp_ms:
            if self.last_exchange_timestamp_ms is not None and exchange_ms - self.last_exchange_timestamp_ms > GAP_MS:
                self.gaps.append(
                    {
                        "from_exchange_timestamp_ms": self.last_exchange_timestamp_ms,
                        "to_exchange_timestamp_ms": exchange_ms,
                        "delta_ms": exchange_ms - self.last_exchange_timestamp_ms,
                    }
                )
            self.last_exchange_timestamp_ms = exchange_ms
        else:
            self.out_of_order_count += 1


def cash_session_open(now: datetime) -> bool:
    local = now.astimezone(IST)
    if local.weekday() >= 5:
        return False
    start = local.replace(hour=CASH_OPEN[0], minute=CASH_OPEN[1], second=0, microsecond=0)
    end = local.replace(hour=CASH_CLOSE[0], minute=CASH_CLOSE[1], second=0, microsecond=0)
    return start <= local <= end


def find_ltpc(entry: dict) -> dict:
    if not isinstance(entry, dict):
        return {}
    direct = entry.get("ltpc")
    if isinstance(direct, dict):
        return direct
    full = entry.get("fullFeed") or entry.get("full_feed") or {}
    if not isinstance(full, dict):
        return {}
    for name in ("indexFF", "index_ff", "marketFF", "market_ff"):
        block = full.get(name) or {}
        if isinstance(block, dict) and isinstance(block.get("ltpc"), dict):
            return block["ltpc"]
    return {}


def as_int_ms(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or not text.lstrip("-").isdigit():
            return None
        value = int(text)
    if isinstance(value, (int, float)):
        number = int(value)
        if number > 1_000_000_000_000:
            return number
        if number > 1_000_000_000:
            return number * 1000
    return None


def observations_from_decoded(decoded: dict, received_at_utc: str) -> list[dict]:
    current = as_int_ms(decoded.get("currentTs") if "currentTs" in decoded else decoded.get("current_ts"))
    message_type = decoded.get("type")
    feeds = decoded.get("feeds") or {}
    if not isinstance(feeds, dict) or not feeds:
        market = decoded.get("marketInfo") or decoded.get("market_info") or {}
        return [
            {
                "kind": "control",
                "received_at_utc": received_at_utc,
                "feed_current_ts_ms": current,
                "message_type": message_type,
                "method": decoded.get("method"),
                "status": decoded.get("status"),
                "market_info_present": bool(market),
            }
        ]
    rows = []
    for key, entry in feeds.items():
        ltpc = find_ltpc(entry if isinstance(entry, dict) else {})
        exchange_ms = as_int_ms(ltpc.get("ltt"))
        rows.append(
            {
                "kind": "ltpc",
                "instrument_key": str(key),
                "received_at_utc": received_at_utc,
                "exchange_timestamp_ms": exchange_ms,
                "exchange_timestamp_present": exchange_ms is not None,
                "feed_current_ts_ms": current,
                "message_type": message_type,
                "ltp": ltpc.get("ltp"),
            }
        )
    return rows


def subscription_acknowledged(row: dict) -> bool:
    if row.get("kind") == "ltpc" and row.get("instrument_key") in KEYS:
        return True
    method = str(row.get("method") or "").lower()
    status = str(row.get("status") or "").lower()
    return method == "sub" and status in {"success", "ok"}


def feed_checkpoint(index: IndexCapture, *, duration_sec: int, dry_run: bool, session_open: bool) -> str:
    if dry_run or not session_open or duration_sec < 600:
        return "not_a_pass"
    if (
        index.subscription_ack
        and index.count > 0
        and index.exchange_timestamp_present > 0
        and index.exchange_timestamp_absent == 0
    ):
        return "pass"
    return "fail"


def summary_document(
    indexes: dict[str, IndexCapture],
    *,
    authorize_status: int | None,
    disconnects: int,
    decode_failures: int,
    duration_sec: int,
    dry_run: bool,
    session_open: bool,
    reason: str,
) -> dict:
    per_index = {}
    for key in KEYS:
        index = indexes[key]
        per_index[key] = {
            "instrument_key": key,
            "subscription_ack": index.subscription_ack,
            "count": index.count,
            "first_exchange_timestamp_ms": index.first_exchange_timestamp_ms,
            "last_exchange_timestamp_ms": index.last_exchange_timestamp_ms,
            "first_received_at_utc": index.first_received_at_utc,
            "last_received_at_utc": index.last_received_at_utc,
            "exchange_timestamp_present": index.exchange_timestamp_present,
            "exchange_timestamp_absent": index.exchange_timestamp_absent,
            "gaps": index.gaps,
            "duplicate_count": index.duplicate_count,
            "out_of_order_count": index.out_of_order_count,
            "feed_checkpoint": feed_checkpoint(
                index, duration_sec=duration_sec, dry_run=dry_run, session_open=session_open
            ),
        }
    any_ticks = any(indexes[key].count > 0 for key in KEYS)
    checkpoints = [per_index[key]["feed_checkpoint"] for key in KEYS]
    return {
        "checkpoint": "F-C01",
        "pass": checkpoints == ["pass", "pass", "pass"],
        "reason": reason,
        "data_available": any_ticks,
        "data_validated": False,
        "signal_eligible": False,
        "entry_eligible": False,
        "authorize_http_status": authorize_status,
        "authenticated": authorize_status == 200,
        "connection_alone_is_not_a_pass": True,
        "dry_run": dry_run,
        "cash_session_open": session_open,
        "duration_sec": duration_sec,
        "disconnects": disconnects,
        "decode_failures": decode_failures,
        "indexes": per_index,
    }


def redact(text: str, secrets: list[str]) -> str:
    cleaned = text
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "[redacted]")
    return cleaned


def subscribe_frame(keys: tuple[str, ...] = KEYS) -> bytes:
    """UTF-8 JSON on a binary websocket frame. A text frame produced no prices."""
    return json.dumps(
        {
            "guid": str(uuid.uuid4()),
            "method": "sub",
            "data": {"mode": "ltpc", "instrumentKeys": list(keys)},
        }
    ).encode("utf-8")


def decode_frame(raw, pb_module):
    if isinstance(raw, str):
        return json.loads(raw)
    if pb_module is None:
        raise RuntimeError("protobuf decoder unavailable")
    from google.protobuf.json_format import MessageToDict

    feed = pb_module.FeedResponse()
    feed.ParseFromString(raw)
    return MessageToDict(feed, preserving_proto_field_name=True)


def load_decoder():
    if not PB2_DIR.is_dir():
        return None
    sys.path.insert(0, str(PB2_DIR))
    import MarketDataFeedV3_pb2 as pb_module

    return pb_module


def authorize(token: str) -> tuple[int, str | None]:
    import requests

    response = requests.get(
        AUTHORIZE_URL,
        headers={"Accept": "application/json", "Authorization": "Bearer " + token},
        timeout=30,
    )
    if response.status_code != 200:
        return response.status_code, None
    payload = response.json()
    data = payload.get("data") or {}
    uri = data.get("authorizedRedirectUri") or data.get("authorized_redirect_uri")
    if not uri or not str(uri).startswith("wss://"):
        return response.status_code, None
    return response.status_code, str(uri)


def capture(token: str, *, duration_sec: int, dry_run: bool, out_dir: Path) -> dict:
    started = datetime.now(timezone.utc)
    session_open = cash_session_open(started)
    indexes = {key: IndexCapture() for key in KEYS}
    disconnects = 0
    decode_failures = 0
    observations: list[dict] = []
    status, uri = authorize(token)
    if status == 200 and uri:
        reason, disconnects, decode_failures = _stream(
            uri,
            token,
            indexes=indexes,
            observations=observations,
            duration_sec=duration_sec,
            dry_run=dry_run,
            counters={"disconnects": 0, "decode_failures": 0},
        )
    else:
        reason = "authorize_failed"
    document = summary_document(
        indexes,
        authorize_status=status,
        disconnects=disconnects,
        decode_failures=decode_failures,
        duration_sec=duration_sec,
        dry_run=dry_run,
        session_open=session_open,
        reason=reason,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
    (out_dir / "summary.json").write_text(redact(encoded, [token, uri or ""]), encoding="utf-8")
    lines = [
        redact(json.dumps(row, sort_keys=True, default=str), [token, uri or ""])
        for row in observations
    ]
    (out_dir / "observations.jsonl").write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return document


def _stream(uri, token, *, indexes, observations, duration_sec, dry_run, counters) -> tuple[str, int, int]:
    import asyncio
    import websockets

    decoder = None
    try:
        decoder = load_decoder()
    except Exception:
        decoder = None
    idle_sec = 15 if dry_run else 30
    deadline = datetime.now(timezone.utc) + timedelta(seconds=duration_sec)

    async def _run() -> str:
        reason = "nothing_to_record"
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=20, close_timeout=5, max_size=8 * 1024 * 1024) as ws:
                await ws.send(subscribe_frame(KEYS))
                while datetime.now(timezone.utc) < deadline:
                    timeout = min(idle_sec, max(1, int((deadline - datetime.now(timezone.utc)).total_seconds())))
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    except asyncio.TimeoutError:
                        if cash_session_open(datetime.now(timezone.utc)) and not dry_run:
                            continue
                        if dry_run or not any(indexes[key].count for key in KEYS):
                            reason = "nothing_to_record"
                            break
                        continue
                    received = datetime.now(timezone.utc).isoformat()
                    try:
                        decoded = decode_frame(raw, decoder)
                    except Exception:
                        counters["decode_failures"] += 1
                        observations.append(
                            {
                                "kind": "decode_failure",
                                "received_at_utc": received,
                                "byte_length": len(raw) if isinstance(raw, (bytes, str)) else None,
                            }
                        )
                        continue
                    if not isinstance(decoded, dict):
                        counters["decode_failures"] += 1
                        continue
                    for row in observations_from_decoded(decoded, received):
                        observations.append(row)
                        key = row.get("instrument_key")
                        if key in indexes and row.get("kind") == "ltpc":
                            indexes[key].subscription_ack = True
                            indexes[key].note(row.get("exchange_timestamp_ms"), received)
                        elif subscription_acknowledged(row):
                            for index in indexes.values():
                                index.subscription_ack = True
                    if dry_run and any(indexes[key].count for key in KEYS):
                        reason = "dry_run_saw_a_frame"
                        break
                else:
                    reason = "duration_complete"
        except Exception as exc:
            counters["disconnects"] += 1
            message = redact(f"{type(exc).__name__}", [token, uri])
            observations.append({"kind": "disconnect", "received_at_utc": datetime.now(timezone.utc).isoformat(), "error_type": message})
            reason = "disconnect"
        else:
            counters["disconnects"] += 1
            observations.append(
                {
                    "kind": "disconnect",
                    "received_at_utc": datetime.now(timezone.utc).isoformat(),
                    "error_type": "clean_close",
                }
            )
        return reason

    outcome = asyncio.run(_run())
    if not cash_session_open(datetime.now(timezone.utc)) and outcome in {"nothing_to_record", "duration_complete", "dry_run_saw_a_frame"}:
        outcome = "closed_session"
    return outcome, counters["disconnects"], counters["decode_failures"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record the Upstox V3 index ltpc feed.")
    parser.add_argument("--duration-sec", type=int, default=600)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.duration_sec < 1:
        print("duration_sec must be positive")
        return 2
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token or token.startswith("PASTE_"):
        print("token missing")
        return 2
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out_dir or Path("/opt/shivtrade/shivai/fc01") / stamp
    if args.dry_run:
        args.duration_sec = min(args.duration_sec, 25)
    document = capture(token, duration_sec=args.duration_sec, dry_run=args.dry_run, out_dir=out_dir)
    print(
        "authorize_http_status",
        document["authorize_http_status"],
        "authenticated",
        document["authenticated"],
        "pass",
        document["pass"],
        "reason",
        document["reason"],
        "disconnects",
        document["disconnects"],
        "decode_failures",
        document["decode_failures"],
    )
    for key in KEYS:
        row = document["indexes"][key]
        print(
            key,
            "ack",
            row["subscription_ack"],
            "count",
            row["count"],
            "exchange_timestamp_present",
            row["exchange_timestamp_present"],
            "checkpoint",
            row["feed_checkpoint"],
        )
    print("wrote", out_dir)
    if document["authorize_http_status"] != 200:
        return int(document["authorize_http_status"] or 1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
