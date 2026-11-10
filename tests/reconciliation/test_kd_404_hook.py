"""Ensure KD retire check script is present and exits 0 on mocked 404."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_kd_404.sh"


def test_check_kd_404_script_exists() -> None:
    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


@pytest.mark.integration
def test_check_kd_404_against_url() -> None:
    if os.environ.get("KD_404_SKIP", "").strip() in ("1", "true", "yes"):
        pytest.skip("KD_404_SKIP set")
    url = os.environ.get(
        "KD_LATEST_URL",
        "https://shivatrade.store/api/kaaldrishti/latest",
    )
    proc = subprocess.run(
        [str(SCRIPT)],
        cwd=ROOT,
        env={**os.environ, "KD_LATEST_URL": url},
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 and "000" in proc.stdout:
        pytest.skip("KD URL unreachable from this runner")
    assert proc.returncode == 0, proc.stdout + proc.stderr
