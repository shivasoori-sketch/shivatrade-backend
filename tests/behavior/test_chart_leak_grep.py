"""CI grep: no price-color verdict assignment in engine sources or UI bundle."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_engine_no_verdict_from_price_color_vars() -> None:
    engine = REPO / "thesis" / "thesis_engine.py"
    text = engine.read_text(encoding="utf-8")
    forbidden = [
        re.compile(r"state\s*=\s*.*\b(candle_color|price_color|momentum)\b"),
        re.compile(r"ThesisState\.\w+\s*if\s+.*\bltp\b.*else"),
    ]
    for pat in forbidden:
        assert not pat.search(text), f"chart leak pattern {pat.pattern} in thesis_engine.py"


def test_ui_bundle_no_badge_interval_or_annotation_animation() -> None:
    root = REPO / "ui-live/kaaldrishti-preview/thesis-card"
    js = (root / "thesis-card.js").read_text(encoding="utf-8", errors="ignore")
    card = (root / "ThesisCard.jsx").read_text(encoding="utf-8")
    mount = (root / "LiveThesisMount.jsx").read_text(encoding="utf-8")
    assert "thesis-annotation" in card
    assert "thesis-badge" in card or "thesis-badge" in js
    ui = (root / "thesisUiConfig.js").read_text(encoding="utf-8")
    assert "Awaiting candle close" in ui
    assert "@keyframes" not in js
    assert "animation:" not in js
    assert "className=\"pulse\"" not in js
    if "setInterval" in mount:
        assert "badge" not in mount.split("setInterval", 1)[1][:120].lower()


BOOK_PENDING_COPY = "Awaiting candle close — book score updates on 1m close."
