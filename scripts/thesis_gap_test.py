#!/usr/bin/env python3
"""Scripted gap test: replay ticks with injected gap; assert data_stale via /ingest/tick."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from thesis.runtime import ThesisRuntime  # noqa: E402


def run_gap_test(*, fixture: Path, gap_symbol: str = "NSE:GAPTEST") -> dict:
    ThesisRuntime.reset()
    client = TestClient(app)
    base = {
        "ltp": 100.0,
        "vtt": 1,
        "tbq": 1,
        "tsq": 1,
        "oi": 1,
    }
    r1 = client.post(
        "/ingest/tick",
        json={"symbol": gap_symbol, "raw": base, "ts": 10.0},
    )
    assert r1.status_code == 200
    stale_after_gap = client.post(
        "/ingest/tick",
        json={"symbol": gap_symbol, "raw": base, "ts": 20.0},
    ).json()["data_stale"]
    cleared = client.post(
        "/ingest/tick",
        json={"symbol": gap_symbol, "raw": base, "ts": 21.0},
    ).json()["data_stale"]

    replay_rows = 0
    if fixture.is_file():
        for line in fixture.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            replay_rows += 1
            client.post(
                "/ingest/tick",
                json={
                    "symbol": row["symbol"],
                    "raw": row["raw"],
                    "ts": row["ts"],
                },
            )

    return {
        "gap_symbol": gap_symbol,
        "data_stale_after_10s_gap": stale_after_gap,
        "data_stale_cleared_on_next_tick": cleared is False,
        "replay_fixture": str(fixture),
        "replay_rows": replay_rows,
        "pass": stale_after_gap is True and cleared is False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="THESIS scripted data_stale gap test")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=ROOT / "tests/fixtures/replay/sample_session.jsonl",
    )
    args = parser.parse_args()
    result = run_gap_test(fixture=args.fixture)
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
