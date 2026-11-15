"""Section 1 layout. Not a server and not mounted on a route."""
from __future__ import annotations

import html

from shivai_r3.snapshot import InstrumentView, close_views, session_views

_CSS = """
label { margin-right: 1rem; }
.split { display: flex; min-height: 16rem; }
.chart, .rows { width: 50%; box-sizing: border-box; }
.chart { border-right: 1px solid #ccc; }
.rows { margin: 0; padding: 0 0 0 1rem; }
.rows div { display: flex; gap: 1rem; padding: 0.4rem 0; border-bottom: 1px solid #eee; }
.rows strong { width: 14rem; }
header dl { display: grid; grid-template-columns: 12rem 1fr; margin: 0 0 1rem; }
.panel { display: none; }
#i-NIFTY:checked ~ .panel-NIFTY,
#i-BANKNIFTY:checked ~ .panel-BANKNIFTY,
#i-SENSEX:checked ~ .panel-SENSEX { display: block; }
@media (max-width: 700px) {
  .split { flex-direction: column; }
  .chart, .rows { width: 100%; }
  .chart { border-right: 0; border-bottom: 1px solid #ccc; }
}
"""


def _header(view: InstrumentView) -> str:
    fields = (
        ("instrument", view.instrument),
        ("price", view.price),
        ("exchange date", view.exchange_date),
        ("source_quality", view.source_quality),
        ("last valid tick", view.last_valid_tick),
        ("last engine assessment", view.last_engine_assessment),
    )
    rows = "".join(
        f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"
        for label, value in fields
    )
    return f"<header><dl>{rows}</dl></header>"


def _panel(view: InstrumentView) -> str:
    body = "".join(
        "<div><strong>{}</strong><span>{}</span></div>".format(
            html.escape(row.title), html.escape(row.value)
        )
        for row in view.five_rows
    )
    return (
        f'<section class="panel panel-{html.escape(view.instrument)}">'
        f"{_header(view)}"
        '<div class="split">'
        '<div class="chart">3-minute spot</div>'
        f'<div class="rows">{body}</div>'
        "</div>"
        "</section>"
    )


def _page(views: tuple[InstrumentView, ...]) -> str:
    controls = []
    panels = []
    for index, view in enumerate(views):
        checked = " checked" if index == 0 else ""
        ident = html.escape(view.instrument)
        controls.append(
            f'<input id="i-{ident}" type="radio" name="instrument"{checked}>'
            f'<label for="i-{ident}">{ident}</label>'
        )
        panels.append(_panel(view))
    # Inputs precede the panels so :checked ~ .panel can show one instrument.
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        f"<title>SHIVAI</title><style>{_CSS}</style></head><body>"
        f'{"".join(controls)}{"".join(panels)}'
        "</body></html>"
    )


def render_closes() -> str:
    return _page(close_views())


def render_session() -> str:
    return _page(session_views())
