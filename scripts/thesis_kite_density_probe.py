#!/usr/bin/env python3
"""Gate 1 — independent WebSocket density probe (separate KiteTicker from thesis-ingest)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from thesis.ingestor.kite_density_probe import run_density_probe_main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_density_probe_main())
