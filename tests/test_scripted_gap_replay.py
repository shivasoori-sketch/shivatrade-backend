"""Scripted gap test wrapper (Gate 1 deterministic)."""

from pathlib import Path

from scripts.thesis_gap_test import run_gap_test


def test_scripted_gap_replay_passes() -> None:
    fixture = Path(__file__).parent / "fixtures/replay/sample_session.jsonl"
    result = run_gap_test(fixture=fixture)
    assert result["data_stale_after_10s_gap"] is True
    assert result["data_stale_cleared_on_next_tick"] is True
    assert result["pass"] is True
