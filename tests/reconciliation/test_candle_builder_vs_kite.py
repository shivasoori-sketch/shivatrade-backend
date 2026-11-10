"""Automated candle builder vs Kite historical_data baseline (replaces manual CSV)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests.reconciliation.kite_baseline import (
    DEFAULT_KITE_FIXTURE,
    DEFAULT_REPLAY_FIXTURE,
    compare_builder_to_kite,
    dedupe_builder_candles,
    fetch_kite_historical_live,
    load_kite_fixture,
    write_reconciliation_report,
)
from thesis.ingestor.session_audit import replay_and_build

REPORT_PATH = Path(
    os.environ.get(
        "RECONCILIATION_REPORT_PATH",
        Path(__file__).resolve().parent / "reconciliation_report.json",
    )
)


def _maybe_live_kite_rows(meta: dict) -> list | None:
    if os.environ.get("THESIS_KITE_LIVE_RECONCILE", "").strip() not in ("1", "true", "yes"):
        return None
    token = meta.get("instrument_token") or os.environ.get("KITE_INSTRUMENT_TOKEN")
    if not token:
        pytest.skip("THESIS_KITE_LIVE_RECONCILE set but instrument_token missing")
    return fetch_kite_historical_live(
        instrument_token=int(token),
        from_date=str(meta.get("from_date")),
        to_date=str(meta.get("to_date")),
        interval=str(meta.get("interval") or "minute"),
    )


@pytest.mark.reconciliation
def test_candle_builder_matches_kite_historical_fixture() -> None:
    assert DEFAULT_REPLAY_FIXTURE.is_file(), "missing VPS replay jsonl slice"
    assert DEFAULT_KITE_FIXTURE.is_file(), "missing Kite historical fixture"

    meta, kite_candles = load_kite_fixture()
    live_rows = _maybe_live_kite_rows(meta)
    if live_rows is not None:
        kite_candles = []
        from tests.reconciliation.kite_baseline import KiteMinuteCandle, _parse_kite_date

        for row in live_rows:
            kite_candles.append(
                KiteMinuteCandle(
                    minute_start=_parse_kite_date(str(row["date"])),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=int(row["volume"]),
                )
            )

    closed, _ticks = replay_and_build(DEFAULT_REPLAY_FIXTURE)
    built = dedupe_builder_candles(closed)

    diffs, report = compare_builder_to_kite(built, kite_candles)
    report["replay_fixture"] = str(DEFAULT_REPLAY_FIXTURE)
    report["kite_fixture"] = str(DEFAULT_KITE_FIXTURE)
    report["live_kite"] = live_rows is not None
    write_reconciliation_report(report, REPORT_PATH)

    assert not diffs, f"Kite reconciliation failed ({len(diffs)} diffs); see {REPORT_PATH}"
