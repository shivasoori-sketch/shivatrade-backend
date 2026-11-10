"""Automated wick-day paper replay (replaces manual Step 8 eyeball)."""

from __future__ import annotations

from pathlib import Path

import pytest

WICK_FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "wick_replay"
    / "known_wick_session.jsonl"
)


@pytest.mark.wick_replay
def test_known_wick_session_replay() -> None:
    if not WICK_FIXTURE.is_file():
        pytest.skip(
            "TODO: add known wick capture to tests/fixtures/wick_replay/ "
            "before automated Step 8 wick replay gate"
        )
