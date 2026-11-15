"""Section 1 layout. Not a server and not mounted on a route."""
from __future__ import annotations

import html
from decimal import Decimal, ROUND_HALF_UP

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
.chart { border-right: 1px solid #dbe3ee; display: flex; flex-direction: column; padding: 8px 12px 8px 16px; }
.chart svg { width: 100%; height: 100%; flex: 1; display: block; min-height: 28rem; }
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


def _svg_y(price: Decimal, upper: Decimal, lower: Decimal) -> str:
    top, bottom = Decimal(56), Decimal(430)
    mapped = top + (upper - price) / (upper - lower) * (bottom - top)
    return format(mapped.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP), "f")


def _chart(candle: tuple[str, str, str, str] | None) -> str:
    # Section 1 chart name. A session with no print has the frame and no bar.
    frame = (
        '<svg viewBox="0 0 640 480" role="img">'
        '<text x="20" y="28" fill="#334155" font-size="14" font-family="sans-serif">3-minute spot</text>'
    )
    if candle is None:
        return frame + "</svg>"
    open_text, high_text, low_text, close_text = candle
    open_, high, low, close = (Decimal(part) for part in candle)
    span = high - low or Decimal("1")
    pad = span * Decimal("0.16")
    upper, lower = high + pad, low - pad
    y_open = _svg_y(open_, upper, lower)
    y_high = _svg_y(high, upper, lower)
    y_low = _svg_y(low, upper, lower)
    y_close = _svg_y(close, upper, lower)
    body_top = y_open if open_ >= close else y_close
    body_bottom = y_close if open_ >= close else y_open
    color = "#b42318" if close < open_ else "#047857"
    series = ",".join(candle)
    path = (
        f"M260 {y_high}L260 {y_low}"
        f"M238 {body_top}L282 {body_top}L282 {body_bottom}L238 {body_bottom}Z"
    )
    labels = []
    for price, y in ((high_text, y_high), (open_text, y_open), (close_text, y_close), (low_text, y_low)):
        weight = "700" if price == close_text else "500"
        labels.append(
            f'<text x="520" y="{y}" fill="#0f172a" font-size="13" font-weight="{weight}" '
            f'font-family="sans-serif">{html.escape(price)}</text>'
        )
    return (
        frame
        + f'<path class="candle" fill="{color}" stroke="{color}" stroke-width="2" '
        + f'data-series="{html.escape(series)}" d="{path}"/>'
        + "".join(labels)
        + '<text x="220" y="462" fill="#475569" font-size="13" font-family="sans-serif">13 Nov 2026</text>'
        + "</svg>"
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
        f'<div class="chart">{_chart(view.candle)}</div>'
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
