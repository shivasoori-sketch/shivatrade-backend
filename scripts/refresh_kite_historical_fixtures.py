#!/usr/bin/env python3
"""Record Kite historical_data into tests/fixtures/kite/ for CI reconciliation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.reconciliation.kite_baseline import fetch_kite_historical_live  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh Kite minute candles fixture")
    parser.add_argument("--instrument-token", type=int, required=True)
    parser.add_argument("--from-date", default="2026-11-09 09:15:00")
    parser.add_argument("--to-date", default="2026-11-09 10:30:00")
    parser.add_argument("--tradingsymbol", default="NIFTY26NOVFUT")
    parser.add_argument("--exchange", default="NFO")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT
        / "tests"
        / "fixtures"
        / "kite"
        / "nfo_nifty26novfut_2026-11-09_0915_1030_ist.json",
    )
    args = parser.parse_args()

    rows = fetch_kite_historical_live(
        instrument_token=args.instrument_token,
        from_date=args.from_date,
        to_date=args.to_date,
    )
    payload = {
        "source": "kite_historical_data",
        "recorded_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "instrument_token": args.instrument_token,
        "tradingsymbol": args.tradingsymbol,
        "exchange": args.exchange,
        "kite_symbol": f"{args.exchange}:{args.tradingsymbol}",
        "thesis_symbol": f"NSE:{args.tradingsymbol}",
        "interval": "minute",
        "from_date": args.from_date,
        "to_date": args.to_date,
        "candles": [
            {
                "date": str(r["date"]),
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": r["volume"],
            }
            for r in rows
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {args.out} ({len(rows)} candles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
