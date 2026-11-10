"""KD removed from conviction slot HTML."""

from pathlib import Path

ROOT = (
    Path(__file__).resolve().parent.parent
    / "ui-live"
    / "kaaldrishti-preview"
)


def test_index_html_thesis_only() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "thesis-card.js" in html
    assert "thesis-card-root" in html
    assert "kd-card.js" not in html
    assert "kd-card-root" not in html


def test_float_preview_thesis_only() -> None:
    html = (ROOT / "KAALDRISHTI-FLOAT-PREVIEW.html").read_text(encoding="utf-8")
    assert "thesis-card.js" in html
    assert "kd-card.js" not in html


def test_full_card_preview_thesis_only() -> None:
    html = (ROOT / "KAALDRISHTI-FULL-CARD-PREVIEW.html").read_text(encoding="utf-8")
    assert "thesis-card-root" in html
    assert "kd-card.js" not in html


def test_no_kd_assessment_js_fallback() -> None:
    for name in (
        "index.html",
        "KAALDRISHTI-FULL-CARD-PREVIEW.html",
        "KAALDRISHTI-FLOAT-PREVIEW.html",
    ):
        html = (ROOT / name).read_text(encoding="utf-8")
        assert "assessment.js" not in html
        assert "/api/kaaldrishti/latest" not in html


def test_external_signals_stub() -> None:
    from fastapi.testclient import TestClient
    from main import app
    from thesis.runtime import ThesisRuntime

    ThesisRuntime.reset()
    c = TestClient(app)
    body = c.get("/external_signals").json()
    assert body["enabled"] is False
    assert body["signals"] == []
