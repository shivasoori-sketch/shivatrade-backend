"""Adviser contract: no preview=live in source; demo query documented."""

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_no_preview_live_string_in_source() -> None:
    banned = "preview=live"
    exclude_dirs = {
        ".git",
        "node_modules",
        "dist",
        ".venv",
        "__pycache__",
        "tests",
        ".github",
    }
    hits: list[str] = []
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        if any(part in exclude_dirs for part in path.parts):
            continue
        if path.suffix in {".png", ".jpg", ".js"} and "thesis-card.js" in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if banned in text:
            hits.append(str(path.relative_to(REPO)))
    assert not hits, f"remove {banned!r} from: {hits}"


def test_demo_holds_fixture_exists() -> None:
    demo = REPO / "ui-live/kaaldrishti-preview/thesis-card/demoScenario.js"
    body = demo.read_text(encoding="utf-8")
    assert "DEMO — static fixtures" in body
    assert "demo=" in body or 'get("demo")' in body
