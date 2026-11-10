"""Golden-style tests for Book-Divergence Engine."""

from __future__ import annotations

import json

import pytest

from thesis.book_engine import BookDivergenceEngine
from thesis.types import FusionWeights
from tests.conftest import make_tick


def test_fusion_weights_must_sum_to_100() -> None:
    with pytest.raises(ValueError):
        FusionWeights(volume=10, oi=10, absorption=10, depth=10)


def test_book_fusion_golden_sequence() -> None:
    engine = BookDivergenceEngine()
    symbol = "NSE:TEST"
    ticks = [
        make_tick(ltp=100.0, ts=1.0, vtt=1000, oi=100_000),
        make_tick(ltp=100.5, ts=2.0, vtt=1200, oi=100_050, tsq=6000, tbq=4000),
        make_tick(ltp=101.0, ts=3.0, vtt=900, oi=100_040, bid_qty=200, ask_qty=180),
        make_tick(ltp=101.2, ts=4.0, vtt=850, oi=100_041, bid_qty=150, ask_qty=140),
    ]
    snapshots = []
    for t in ticks:
        out = engine.evaluate(symbol, t)
        snapshots.append(
            {
                "book_score": out.book_score,
                "divergence_flag": out.divergence_flag,
                "sweep_risk": out.sweep_risk,
                "sub_scores": {
                    "absorption": out.sub_scores.absorption,
                    "liquidity_vacuum": out.sub_scores.liquidity_vacuum,
                    "oi_confirmation": out.sub_scores.oi_confirmation,
                    "volume_follow_through": out.sub_scores.volume_follow_through,
                },
            }
        )
    golden = json.dumps(snapshots, sort_keys=True)
    assert golden == (
        '[{"book_score": 57, "divergence_flag": false, "sub_scores": '
        '{"absorption": 55, "liquidity_vacuum": 88, "oi_confirmation": 50, '
        '"volume_follow_through": 50}, "sweep_risk": false}, '
        '{"book_score": 73, "divergence_flag": false, "sub_scores": '
        '{"absorption": 85, "liquidity_vacuum": 88, "oi_confirmation": 80, '
        '"volume_follow_through": 50}, "sweep_risk": false}, '
        '{"book_score": 38, "divergence_flag": true, "sub_scores": '
        '{"absorption": 55, "liquidity_vacuum": 33, "oi_confirmation": 25, '
        '"volume_follow_through": 40}, "sweep_risk": false}, '
        '{"book_score": 54, "divergence_flag": false, "sub_scores": '
        '{"absorption": 55, "liquidity_vacuum": 30, "oi_confirmation": 80, '
        '"volume_follow_through": 40}, "sweep_risk": false}]'
    )


def test_sweep_risk_after_persistent_depth_pull() -> None:
    engine = BookDivergenceEngine(depth_pull_ticks_required=2)
    symbol = "NSE:SWEEP"
    base = 200.0
    for i in range(8):
        ltp = base + i * 0.3
        make = make_tick(
            ltp=ltp,
            ts=float(i),
            vtt=500 + i * 50,
            oi=50_000,
            bid_qty=900 - i * 80,
            ask_qty=900 - i * 80,
        )
        engine.evaluate(symbol, make)

    sweep_tick = make_tick(
        ltp=base + 3.0,
        ts=9.0,
        vtt=400,
        oi=50_000,
        bid_qty=80,
        ask_qty=70,
        spread=0.5,
        tsq=8000,
        tbq=2000,
    )
    out = engine.evaluate(symbol, sweep_tick)
    assert out.sweep_risk is True
    assert out.sub_scores.volume_follow_through <= 40


def test_weighted_fusion_formula() -> None:
    engine = BookDivergenceEngine(FusionWeights())
    tick = make_tick(ltp=50.0, ts=0.0, vtt=2000, tsq=7000, tbq=3000, oi=10_000)
    out = engine.evaluate("SYM", tick)
    subs = out.sub_scores
    expected = (
        subs.volume_follow_through * 30
        + subs.oi_confirmation * 30
        + subs.absorption * 25
        + subs.liquidity_vacuum * 15
    ) / 100.0
    assert out.book_score == int(max(0, min(100, round(expected))))
