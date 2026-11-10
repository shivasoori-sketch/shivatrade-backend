"""Sanity checks for THESIS card static bundle."""

from pathlib import Path


def test_thesis_card_bundle_exists() -> None:
    root = (
        Path(__file__).resolve().parent.parent
        / "ui-live"
        / "kaaldrishti-preview"
        / "thesis-card"
    )
    assert (root / "thesis-card.js").is_file()
    assert (root / "thesis-card.css").is_file()
    js = (root / "thesis-card.js").read_text(encoding="utf-8")
    assert "THESIS" in js or "thesis" in js
