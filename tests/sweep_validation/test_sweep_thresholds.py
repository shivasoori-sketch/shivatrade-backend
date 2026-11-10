"""Gate 2 — 50+50 sweep vs clean breakout validation (Kite historical days)."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "sweep_validation"


@pytest.mark.sweep_validation
def test_sweep_validation_thresholds() -> None:
    manifest = FIXTURE_ROOT / "manifest.json"
    if not manifest.is_file():
        pytest.skip(
            "TODO: load 50 sweep + 50 clean Kite historical days into "
            "tests/fixtures/sweep_validation/ before enabling Gate 2 thresholds"
        )
