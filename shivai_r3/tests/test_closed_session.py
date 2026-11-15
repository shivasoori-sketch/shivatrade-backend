"""Section 1 view of the Friday closes. Values come from the reference kernel."""
from __future__ import annotations

import ast
import re
import socket
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from shivai_r3.closes import load_closes, unix_ms
from shivai_r3.page import render_closes, render_session
from shivai_r3.reference.shivai_core import Quality, research_snapshot, BreakoutEpisode, Zone
from shivai_r3.snapshot import ROW_TITLES, close_views, session_views

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "shivai_r3"
ABSENT = re.compile(
    r"CLOSED/HISTORICAL|DATA_STALE|NO VALID TRADE|LIVE_VERIFIED|MARKET_CLOSED|"
    r"\bBUY\b|\bSELL\b|\bT1\b|\bT2\b|\bT3\b|support|resistance|trigger|UPDATING"
)


def _without_library(page: str) -> str:
    start = page.index('<script id="lw-lib">')
    end = page.index("</script>", start)
    return page[:start] + page[end:]


class CloseViewTests(unittest.TestCase):
    def test_three_friday_closes(self):
        closes = load_closes()
        self.assertEqual(
            [(c.instrument, c.close_text) for c in closes],
            [("NIFTY 50", "25144.3"), ("BANKNIFTY", "61034.1"), ("SENSEX", "81592.45")],
        )
        self.assertEqual(closes[0].close, Decimal("25144.3"))
        nifty_ms = unix_ms(datetime(2026, 11, 13, 10, 30, tzinfo=timezone.utc))
        sensex_ms = unix_ms(datetime(2026, 11, 13, 10, 29, 59, 508000, tzinfo=timezone.utc))
        self.assertEqual(closes[0].exchange_timestamp_ms, nifty_ms)
        self.assertEqual(closes[2].exchange_timestamp_ms, sensex_ms)
        self.assertEqual(nifty_ms - sensex_ms, 492)
        self.assertNotEqual(closes[0].exchange_timestamp_text, closes[0].audit_api_clock_text)

    def test_view_uses_reference_constants_and_drops_the_dummy_zone(self):
        dummy = research_snapshot(
            0,
            BreakoutEpisode(Zone("unused", 1, "UNUSED", Decimal("1"), "RESISTANCE", 0), Decimal("1")),
            Quality.STALE,
        )
        views = close_views()
        self.assertEqual([view.instrument for view in views], ["NIFTY", "BANKNIFTY", "SENSEX"])
        self.assertEqual([view.price for view in views], ["25144.3", "61034.1", "81592.45"])
        for view in views:
            self.assertEqual(view.exchange_date, "2026-11-13")
            self.assertEqual(view.source_quality, "STALE")
            self.assertEqual(view.last_valid_tick, "")
            self.assertEqual(view.last_engine_assessment, "")
            self.assertEqual(view.chart_overlays, ())
            self.assertEqual(len(view.three_minute_bars), 125)
            self.assertEqual(view.three_minute_bars[0].time_ist[:10], "2026-11-13")
            self.assertEqual(view.three_minute_bars[-1].time_ist, "2026-11-13T15:27:00+05:30")
            self.assertEqual(view.price, view.three_minute_bars[-1].close)
            self.assertEqual(view.snapshot_seq, views[0].snapshot_seq)
            for bar in view.three_minute_bars:
                self.assertNotEqual((bar.open, bar.high, bar.low, bar.close), view.candle)
            self.assertEqual(
                view.candle,
                {
                    "NIFTY": ("25209.85", "25246.35", "25054.4", "25144.3"),
                    "BANKNIFTY": ("61300.55", "61300.55", "60780.55", "61034.1"),
                    "SENSEX": ("81833.78", "81879.51", "81288.75", "81592.45"),
                }[view.instrument],
            )
            self.assertFalse(view.entry_eligible)
            self.assertEqual(view.reject_reasons, tuple(dummy["reject_reasons"]))
            self.assertEqual(tuple(row.title for row in view.five_rows), ROW_TITLES)
            self.assertEqual(view.five_rows[0].value, dummy["five_insights"]["market_trend"])
            self.assertEqual(view.five_rows[1].value, "")
            self.assertEqual(view.five_rows[2].value, "")
            self.assertEqual(view.five_rows[3].value, dummy["five_insights"]["trade_guardian"])
            self.assertEqual(view.five_rows[4].value, dummy["five_insights"]["trade_plan"])
            self.assertNotEqual(view.five_rows[1].value, dummy["five_insights"]["opportunity_zone"])
            self.assertNotIn("unused", view.five_rows[1].value)

    def test_unproven_session_is_degraded_and_blank(self):
        for view in session_views():
            self.assertEqual(view.source_quality, "DEGRADED")
            self.assertEqual(view.price, "")
            self.assertEqual(view.exchange_date, "")
            self.assertEqual(view.last_valid_tick, "")
            self.assertEqual(view.last_engine_assessment, "")
            self.assertEqual(view.chart_overlays, ())
            self.assertEqual(view.three_minute_bars, ())
            self.assertIsNone(view.candle)
            self.assertFalse(view.entry_eligible)
            self.assertEqual(view.five_rows[4].value, "NO_VALID_TRADE")

    def test_page_is_section_1_layout(self):
        page = render_closes()
        self.assertIn("width: 50%", page)
        self.assertIn("flex-direction: column", page)
        self.assertIn("padding: 16px 28px", page)
        self.assertIn("TradingView Lightweight Charts™ v5.3.0", page)
        self.assertIn("LightweightCharts.CandlestickSeries", page)
        self.assertIn("series.setData(item.bars)", page)
        self.assertNotIn('"bars":[]', page)
        self.assertEqual(page.count('"time":'), 375)
        self.assertEqual(page.count('"price_lines":[]'), 3)
        self.assertEqual(page.count('"markers":[]'), 3)
        self.assertEqual(page.count("snapshot_seq 0"), 6)
        self.assertEqual(page.count("125 candles"), 3)
        self.assertIn("09:15-15:27 IST", page)
        self.assertIn("/minutes/3/", page)
        self.assertIn("NSE_INDEX|Nifty 50", page)
        self.assertIn("NSE_INDEX|Nifty Bank", page)
        self.assertIn("BSE_INDEX|SENSEX", page)
        chrome = _without_library(page)
        self.assertNotIn("25209.85,25246.35,25054.4,25144.3", chrome)
        self.assertNotIn("13 Nov 2026", chrome)
        self.assertNotIn("<path", chrome)
        self.assertNotIn("<svg", chrome)
        self.assertEqual(page.count("3-minute spot"), 3)
        for title in ROW_TITLES:
            self.assertEqual(page.count(title), 3)
        for label in ("instrument", "price", "exchange date", "source_quality", "last valid tick", "last engine assessment"):
            self.assertEqual(page.count(f"<dt>{label}</dt>"), 3)
        self.assertIn("25144.3", page)
        self.assertIn("61034.1", page)
        self.assertIn("81592.45", page)
        self.assertIn("2026-11-13", page)
        self.assertIn(">STALE<", page)
        self.assertIn("NO_VALID_TRADE", page)
        self.assertNotIn("ENTRY_POLICY_DISABLED", page)
        self.assertIn("RESEARCH_ONLY", page)
        self.assertIn("UNDETERMINED", page)
        self.assertIsNone(ABSENT.search(_without_library(page)))
        self.assertNotIn("unused", page)
        library = (PACKAGE / "vendor" / "lightweight-charts.standalone.production.js").read_text(
            encoding="utf-8"
        )[:240]
        self.assertIn("TradingView Lightweight Charts™ v5.3.0", library)
        nifty = page.find('id="i-NIFTY"')
        self.assertGreater(nifty, 0)
        self.assertLess(nifty, page.find("<nav"))
        self.assertLess(page.find("</nav>"), page.find('class="panel panel-NIFTY"'))
        session = render_session()
        self.assertIn(">DEGRADED<", session)
        self.assertIsNone(ABSENT.search(_without_library(session)))
        self.assertEqual(session.count('"bars":[]'), 3)
        self.assertNotIn("25144.3", session)
        self.assertNotIn("<path", _without_library(session))

    def test_build_does_not_open_a_socket(self):
        def boom(*_args, **_kwargs):
            raise AssertionError("socket opened")

        with patch.object(socket, "socket", boom), patch.object(socket, "create_connection", boom):
            self.assertEqual(len(close_views()), 3)

    def test_product_modules_do_not_import_a_client_or_the_server(self):
        product = [
            PACKAGE / "closes.py",
            PACKAGE / "gaps.py",
            PACKAGE / "snapshot.py",
            PACKAGE / "page.py",
            PACKAGE / "__init__.py",
            PACKAGE / "__main__.py",
            PACKAGE / "reference" / "shivai_core.py",
        ]
        forbidden = {
            "fastapi", "uvicorn", "kiteconnect", "requests", "httpx", "aiohttp",
            "urllib", "socket", "websocket", "websockets", "paramiko", "subprocess",
        }
        banned_calls = {"write_text", "write_bytes", "mkdir", "unlink"}
        for path in product:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn(alias.name.split(".")[0], forbidden, path.name)
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotIn((node.module or "").split(".")[0], forbidden, path.name)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotEqual(node.func.id, "open", path.name)
                elif isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, banned_calls, path.name)
        for name in ("main.py", "strategy.py", "state.py"):
            for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
                self.assertNotIn("shivai", line.lower(), name)


if __name__ == "__main__":
    unittest.main()
