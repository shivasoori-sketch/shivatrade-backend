"""Section 1 layout. Not a server and not mounted on a route."""
from __future__ import annotations

import html

from shivai_r3.snapshot import InstrumentView, close_views, session_views

_CSS = """
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #fff;
  color: #0f172a;
  font: 16px/1.4 system-ui, sans-serif;
}
.switch { display: flex; gap: 8px; padding: 14px 28px; border-bottom: 1px solid #dbe3ee; }
.switch input { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); border: 0; }
.switch label { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 14px; cursor: pointer; }
.switch input:checked + label { background: #0f172a; color: #fff; border-color: #0f172a; }
.panel { display: none; flex: 1; min-height: 0; flex-direction: column; }
#i-NIFTY:checked ~ .panel-NIFTY,
#i-BANKNIFTY:checked ~ .panel-BANKNIFTY,
#i-SENSEX:checked ~ .panel-SENSEX { display: flex; }
header { border-bottom: 1px solid #dbe3ee; }
header dl { display: flex; flex-wrap: wrap; gap: 18px 32px; margin: 0; padding: 16px 28px; }
header dl div { display: flex; flex-direction: column; gap: 2px; min-width: max-content; }
header dt, header dd { margin: 0; padding: 0; overflow: visible; white-space: nowrap; }
header dt { color: #475569; font-size: 13px; font-weight: 650; }
header dd { min-height: 1.4em; font-size: 18px; font-weight: 700; }
.split { display: flex; flex: 1; min-height: 0; align-items: stretch; }
.chart, .rows { width: 50%; flex: 1 1 50%; min-width: 0; min-height: 0; }
.chart { border-right: 1px solid #dbe3ee; display: flex; flex-direction: column; padding: 12px 0 12px 16px; }
.plot { flex: 1; min-height: 0; display: grid; grid-template-columns: 1fr 6.5rem; grid-template-rows: auto 1fr; }
.chart-name { grid-column: 1 / -1; margin: 0 0 8px; font-size: 13px; font-weight: 650; }
.candles { position: relative; background-color: #fff; background-image: repeating-linear-gradient(to bottom, rgba(15,23,42,0.10) 0 1px, transparent 1px 56px), repeating-linear-gradient(to right, rgba(15,23,42,0.06) 0 1px, transparent 1px 48px); border: 1px solid #d5deea; border-right: 0; }
.scale { position: relative; border: 1px solid #d5deea; border-left: 0; background: #fff; }
.print { position: absolute; top: 50%; right: 8px; width: 8px; height: 8px; margin-top: -4px; background: #0f172a; border-radius: 50%; }
.scale b { position: absolute; top: 50%; right: 8px; transform: translateY(-50%); background: #0f172a; color: #fff; font-size: 13px; font-weight: 700; padding: 3px 7px; border-radius: 3px; }
.rows { margin: 0; padding: 0; display: flex; flex-direction: column; }
.rows div { flex: 1 1 0; display: flex; align-items: center; gap: 16px; min-height: 4.75rem; padding: 0 28px; border-bottom: 1px solid #e2e8f0; }
.rows strong { width: 16rem; flex: 0 0 16rem; font-size: 15px; }
.rows span { font-size: 20px; font-weight: 700; min-height: 1.2em; }
@media (max-width: 700px) {
  .split { flex-direction: column; }
  .chart, .rows { width: 100%; flex-basis: auto; min-height: 50vh; }
  .chart { border-right: 0; border-bottom: 1px solid #dbe3ee; }
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
    cells = "".join(
        "<div><dt>{}</dt><dd>{}</dd></div>".format(html.escape(label), html.escape(value))
        for label, value in fields
    )
    return f"<header><dl>{cells}</dl></header>"


def _chart(price: str) -> str:
    # One print only. No candle is drawn when open, high, and low were not observed.
    mark = ""
    if price:
        shown = html.escape(price)
        mark = f'<span class="print"></span></div><div class="scale"><b>{shown}</b></div>'
    else:
        mark = '</div><div class="scale"></div>'
    return (
        '<div class="plot">'
        '<p class="chart-name">3-minute spot</p>'
        f'<div class="candles">{mark}'
        "</div>"
    )


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
        f'<div class="chart">{_chart(view.price)}</div>'
        f'<div class="rows">{body}</div>'
        "</div>"
        "</section>"
    )


def _page(views: tuple[InstrumentView, ...]) -> str:
    controls = ['<nav class="switch">']
    panels = []
    for index, view in enumerate(views):
        checked = " checked" if index == 0 else ""
        ident = html.escape(view.instrument)
        controls.append(
            f'<input id="i-{ident}" type="radio" name="instrument"{checked}>'
            f'<label for="i-{ident}">{ident}</label>'
        )
        panels.append(_panel(view))
    controls.append("</nav>")
    # Inputs precede the panels so :checked ~ .panel can show one instrument.
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>SHIVAI</title><style>{_CSS}</style></head><body>"
        f'{"".join(controls)}{"".join(panels)}'
        "</body></html>"
    )


def render_closes() -> str:
    return _page(close_views())


def render_session() -> str:
    return _page(session_views())
