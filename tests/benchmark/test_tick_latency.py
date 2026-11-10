"""Latency budget for ingest + engines on VPS-class hardware."""

from __future__ import annotations

import os
import time

import pytest

from tests.conftest import make_tick
from thesis.runtime import ThesisRuntime


@pytest.mark.benchmark
def test_tick_path_latency_budget() -> None:
    budget_ms = float(os.environ.get("THESIS_TICK_LATENCY_MS", "50"))
    ThesisRuntime.reset()
    rt = ThesisRuntime.get()
    tick = make_tick(ltp=25000.0, ts=time.time())

    raw = {
        "last_price": tick.ltp,
        "last_traded_quantity": tick.ltq,
        "volume_traded": tick.vtt,
        "oi": tick.oi,
    }
    start = time.perf_counter()
    for i in range(200):
        rt.ingestor.on_raw_tick(
            "NSE:NIFTY26NOVFUT",
            raw,
            timestamp=tick.timestamp + i * 0.001,
        )
    elapsed_ms = (time.perf_counter() - start) * 1000 / 200

    if os.environ.get("THESIS_BENCHMARK_STRICT", "").strip() not in ("1", "true", "yes"):
        pytest.skip(
            f"TODO: enable THESIS_BENCHMARK_STRICT=1 on VPS ingest path "
            f"(sample mean {elapsed_ms:.2f}ms vs {budget_ms}ms budget)"
        )

    assert elapsed_ms < budget_ms, f"mean tick latency {elapsed_ms:.2f}ms exceeds {budget_ms}ms"
