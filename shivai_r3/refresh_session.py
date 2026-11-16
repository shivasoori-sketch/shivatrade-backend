"""Replace the stored 3-minute session when Upstox returns a later completed one.

The only request is GET /v3/historical-candle/{instrument_key}/minutes/3/{to_date}/{from_date}.
This module does not open a live socket. A non-200 response leaves the stored bars in place.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from shivai_r3.page import render_closes
from shivai_r3.snapshot import THREE_MINUTE_PATH, parse_session_payload

KEYS = (
    "NSE_INDEX|Nifty 50",
    "NSE_INDEX|Nifty Bank",
    "BSE_INDEX|SENSEX",
)
CALL_PATH = "/v3/historical-candle/{instrument_key}/minutes/3/{to_date}/{from_date}"
IST = ZoneInfo("Asia/Kolkata")
TOKEN_FILE = Path("/opt/shivtrade/shared/state/upstox_token.txt")
INDEX_FILE = Path("/opt/shivtrade/shivai/index.html")


def latest_shared_date(series: dict[str, list]) -> str:
    if set(series) != set(KEYS):
        raise ValueError("the three indexes did not all return candles")
    found = set()
    for rows in series.values():
        if not rows:
            raise ValueError("an index returned no candles")
        found.add(max(str(row[0])[:10] for row in rows))
    if len(found) != 1:
        raise ValueError("the indexes do not share one latest session")
    return found.pop()


def session_is_complete(rows: list) -> bool:
    last = max(rows, key=lambda row: str(row[0]))
    return str(last[0])[11:16] >= "15:27"


def plan(stored_date: str, latest_date: str, complete: bool) -> str:
    if latest_date > stored_date and complete:
        return "replace"
    return "keep"


def rows_on_date(rows: list, session_date: str) -> list:
    chosen = [row for row in rows if str(row[0]).startswith(session_date)]
    chosen.sort(key=lambda row: str(row[0]))
    return chosen


def main() -> int:
    import requests

    token_path = Path(os.environ.get("SHIVAI_TOKEN_FILE", TOKEN_FILE))
    token = token_path.read_text(encoding="utf-8").strip()
    if not token or token.startswith("PASTE_"):
        print("token missing")
        return 2
    today = datetime.now(IST).date()
    to_date = today.isoformat()
    from_date = (today - timedelta(days=10)).isoformat()
    http = requests.Session()
    http.headers.update({"Accept": "application/json", "Authorization": "Bearer " + token})
    raw: dict[str, list] = {}
    for key in KEYS:
        url = "https://api.upstox.com" + CALL_PATH.format(
            instrument_key=key, to_date=to_date, from_date=from_date
        )
        response = http.get(url, timeout=45)
        print(key, "status", response.status_code)
        if response.status_code != 200:
            print("stopped", response.status_code)
            return response.status_code
        payload = json.loads(response.text, parse_float=str, parse_int=str)
        raw[key] = ((payload.get("data") or {}).get("candles") or [])
    latest = latest_shared_date(raw)
    stored = json.loads(THREE_MINUTE_PATH.read_text(encoding="utf-8"))
    stored_date = stored["session_date"]
    complete = all(session_is_complete(rows_on_date(raw[key], latest)) for key in KEYS)
    action = plan(stored_date, latest, complete)
    print("stored", stored_date, "latest", latest, "complete", complete, "action", action)
    if action == "keep":
        return 0
    series = {key: rows_on_date(raw[key], latest) for key in KEYS}
    old_seq = stored.get("snapshot_seq", 0)
    document = {
        "session_date": latest,
        "snapshot_seq": old_seq + 1,
        "http_status": 200,
        "to_date": to_date,
        "from_date": from_date,
        "unit": "minutes",
        "interval": "3",
        "series": series,
    }
    parse_session_payload(document)
    THREE_MINUTE_PATH.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    index_path = Path(os.environ.get("SHIVAI_INDEX", INDEX_FILE))
    index_path.write_text(render_closes(), encoding="utf-8")
    print("wrote", latest, "snapshot_seq", old_seq + 1)
    print("restart: systemctl restart shivtrade-shivai.service")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
