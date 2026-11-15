"""Section 1 layout. Not a server and not mounted on a route."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from shivai_r3.snapshot import InstrumentView, ThreeMinuteBar, close_views, session_views

_LIBRARY = Path(__file__).resolve().parent / "vendor" / "lightweight-charts.standalone.production.js"
_DECIMAL = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
_UPSTOX_CALL = (
    "GET https://api.upstox.com/v3/historical-candle/"
    "{instrument_key}/minutes/3/{to_date}/{from_date}"
)

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
.switch-input { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0 0 0 0); border: 0; }
.switch label { border: 1px solid #cbd5e1; border-radius: 6px; padding: 6px 14px; cursor: pointer; }
#i-NIFTY:checked ~ .switch label[for="i-NIFTY"],
#i-BANKNIFTY:checked ~ .switch label[for="i-BANKNIFTY"],
#i-SENSEX:checked ~ .switch label[for="i-SENSEX"] { background: #0f172a; color: #fff; border-color: #0f172a; }
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
.chart { border-right: 1px solid #dbe3ee; display: flex; flex-direction: column; padding: 8px 12px 12px 16px; }
.lw-chart { width: 100%; flex: 1; display: block; min-height: 28rem; }
.chart-name, .seq, .chart-note { margin: 0; }
.chart-name, .seq { padding: 4px 0; }
.chart-note { padding-top: 8px; color: #475569; font-size: 14px; }
.rows { margin: 0; padding: 0; display: flex; flex-direction: column; }
.rows .seq { padding: 12px 28px 0; }
.rows div { flex: 1 1 0; display: flex; align-items: center; gap: 16px; min-height: 4.75rem; padding: 0 28px; border-bottom: 1px solid #e2e8f0; }
.rows strong { width: 19rem; flex: 0 0 19rem; font-size: 15px; white-space: nowrap; }
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


def _seq(view: InstrumentView) -> str:
    return f'<p class="seq">snapshot_seq {html.escape(str(view.snapshot_seq))}</p>'


def _chart(view: InstrumentView) -> str:
    if view.three_minute_bars:
        first = view.three_minute_bars[0].time_ist[11:16]
        last = view.three_minute_bars[-1].time_ist[11:16]
        note = (
            f"{len(view.three_minute_bars)} candles · {view.exchange_date} · "
            f"{first}-{last} IST · {view.instrument_key} · /minutes/3/"
        )
    else:
        note = (
            "No 3-minute candles are on this machine. "
            f"source_quality {view.source_quality}. Required call: {_UPSTOX_CALL} "
            f"with instrument_key {view.instrument_key}."
        )
    return (
        '<div class="chart">'
        '<p class="chart-name">3-minute spot</p>'
        f"{_seq(view)}"
        f'<div id="chart-{html.escape(view.instrument)}" class="lw-chart"></div>'
        f'<p class="chart-note">{html.escape(note)}</p>'
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
        f"{_chart(view)}"
        f'<div class="rows">{_seq(view)}{body}</div>'
        "</div>"
        "</section>"
    )


def _bar_json(bar: ThreeMinuteBar) -> str:
    for token in (bar.open, bar.high, bar.low, bar.close):
        if _DECIMAL.fullmatch(token) is None:
            raise ValueError("bar price is not a decimal")
    return (
        f'{{"time":{bar.unix_s},"open":{bar.open},"high":{bar.high},'
        f'"low":{bar.low},"close":{bar.close}}}'
    )


def _library(views: tuple[InstrumentView, ...]) -> str:
    source = _LIBRARY.read_text(encoding="utf-8")
    if "TradingView Lightweight Charts™ v5.3.0" not in source[:240]:
        raise ValueError("unexpected lightweight-charts build")
    if "</script" in source.lower():
        raise ValueError("library cannot be inlined")
    items = []
    sequences = {view.snapshot_seq for view in views}
    if len(sequences) != 1:
        raise ValueError("snapshot_seq is not shared")
    for view in views:
        if view.chart_overlays:
            raise ValueError("a level was not computed")
        bars = "[" + ",".join(_bar_json(bar) for bar in view.three_minute_bars) + "]"
        items.append(
            "{"
            f'"host":{json.dumps("chart-" + view.instrument)},'
            f'"snapshot_seq":{view.snapshot_seq},'
            f'"bars":{bars},'
            '"price_lines":[],"markers":[]}'
        )
    data = "[" + ",".join(items) + "]"
    return (
        f'<script id="lw-lib">{source}</script>'
        f'<script type="application/json" id="shivai-charts">{data}</script>'
        "<script>"
        "function formatIst(time){"
        "var shifted=new Date((time+19800)*1000);"
        "var p=function(n){return (n<10?'0':'')+n;};"
        "return shifted.getUTCFullYear()+'-'+p(shifted.getUTCMonth()+1)+'-'+p(shifted.getUTCDate())"
        "+' '+p(shifted.getUTCHours())+':'+p(shifted.getUTCMinutes());}"
        "var payload=JSON.parse(document.getElementById('shivai-charts').textContent);"
        "var seq=payload[0].snapshot_seq;"
        "payload.forEach(function(item){"
        "if(item.snapshot_seq!==seq){throw new Error('snapshot_seq diverged');}"
        "var chart=LightweightCharts.createChart(document.getElementById(item.host),"
        "{autoSize:true,layout:{background:{color:'#ffffff'},textColor:'#0f172a'},"
        "localization:{timeFormatter:formatIst},"
        "timeScale:{timeVisible:true,secondsVisible:false,tickMarkFormatter:formatIst}});"
        "var series=chart.addSeries(LightweightCharts.CandlestickSeries);"
        "series.setData(item.bars);"
        "chart.timeScale().fitContent();"
        "item.price_lines.forEach(function(line){series.createPriceLine(line);});"
        "if(item.markers.length){series.setMarkers(item.markers);}"
        "});"
        "</script>"
    )


def _page(views: tuple[InstrumentView, ...]) -> str:
    # Radios are siblings before the panels. A nav around them hides every panel,
    # because :checked ~ .panel cannot see out of that nav.
    inputs = []
    labels = ['<nav class="switch">']
    panels = []
    for index, view in enumerate(views):
        checked = " checked" if index == 0 else ""
        ident = html.escape(view.instrument)
        inputs.append(
            f'<input id="i-{ident}" class="switch-input" type="radio" name="instrument"{checked}>'
        )
        labels.append(f'<label for="i-{ident}">{ident}</label>')
        panels.append(_panel(view))
    labels.append("</nav>")
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>SHIVAI</title><style>{_CSS}</style></head><body>"
        f'{"".join(inputs)}{"".join(labels)}{"".join(panels)}'
        f"{_library(views)}"
        "</body></html>"
    )


def render_closes() -> str:
    return _page(close_views())


def render_session() -> str:
    return _page(session_views())
