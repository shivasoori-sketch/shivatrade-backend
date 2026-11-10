"""Byte-frozen golden outputs for thesis state machine (expand before Phase 2)."""

from __future__ import annotations

from pathlib import Path

import pytest

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "golden"


def test_golden_directory_scaffold() -> None:
    """Placeholder until transition sequences are frozen from live/replay captures."""
    assert GOLDEN_DIR.parent.is_dir()
    if not any(GOLDEN_DIR.glob("*.json")):
        pytest.xfail(
            "TODO: freeze golden transition JSON under tests/fixtures/golden/ "
            "after Step 5 golden capture"
        )
