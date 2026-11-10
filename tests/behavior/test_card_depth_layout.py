"""Card must expose adviser depth sections in source order (not a chart)."""

from pathlib import Path

CARD = Path(__file__).resolve().parents[2] / "ui-live/kaaldrishti-preview/thesis-card/ThesisCard.jsx"


def test_card_section_order_in_source() -> None:
    text = CARD.read_text(encoding="utf-8")
    anchor = text.find("const depth = state?.depth")
    assert anchor >= 0
    text = text[anchor:]
    markers = [
        "thesis-head",
        "thesis-checklist",
        "<DepthPanel",
        "thesis-annotation",
        "thesis-book",
        "thesis-book-pending",
        "thesis-levels",
        "thesis-decision",
    ]
    positions = []
    for m in markers:
        idx = text.find(m)
        if idx >= 0:
            positions.append((idx, m))
    positions.sort()
    ordered = [m for _, m in positions]
    assert ordered.index("thesis-head") < ordered.index("thesis-checklist")
    assert ordered.index("thesis-checklist") < ordered.index("<DepthPanel")
    if "thesis-annotation" in ordered:
        assert ordered.index("<DepthPanel") < ordered.index("thesis-annotation")
    assert ordered.index("thesis-decision") > ordered.index("thesis-levels")


def test_checklist_labels_plain_english_in_demo() -> None:
    demo = Path(__file__).resolve().parents[2] / "ui-live/kaaldrishti-preview/thesis-card/demoScenario.js"
    body = demo.read_text(encoding="utf-8")
    assert "HTF" in body or "session VWAP" in body
    assert "label:" in body
    assert "snake_case" not in body
