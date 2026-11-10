"""Replay real VPS-backed capture slice (last closed session backfill)."""

from __future__ import annotations

from pathlib import Path

from thesis.ingestor.session_audit import audit_capture_file, compare_candles, replay_and_build

FIXTURE = (
    Path(__file__).parent / "fixtures" / "replay" / "vps_nifty_fut_2026-11-09_slice.jsonl"
)


def test_vps_slice_field_coverage() -> None:
    audit = audit_capture_file(FIXTURE)
    assert audit.lines >= 50
    assert audit.populated["ltp"] == audit.lines
    assert audit.populated.get("oi", 0) == audit.lines
    assert audit.populated.get("vtt", 0) == audit.lines
    assert audit.populated.get("depth", 0) == audit.lines
    assert audit.ltq_zero <= 2


def test_vps_slice_candles_match_reference() -> None:
    closed, ticks = replay_and_build(FIXTURE)
    assert len(ticks) >= 50
    assert len(closed) >= 50
    matched, mismatches = compare_candles(closed, ticks)
    assert mismatches == 0
    assert matched == len(closed)
