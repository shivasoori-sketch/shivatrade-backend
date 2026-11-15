"""Closed-session snapshots for the Friday 13 Nov 2026 prints."""
from __future__ import annotations

import ast
import json
import re
import socket
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from shivai_r3.closes import IST, load_closes, unix_ms
from shivai_r3.snapshot import (
    REJECTION_PRECEDENCE,
    ROW_TITLES,
    STAGE_ASSESSMENT,
    build_closed_snapshot,
    build_closed_snapshots,
    outside_regular_session,
    payload_hash,
    to_plain,
)

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "shivai_r3"
BANNED_TEXT = re.compile(
    r"\b(BUY|SELL|LIVE_VERIFIED|BREAKOUT_CONFIRMED_RESEARCH|"
    r"VIRTUAL_OPEN|CONFIRMED_ENTRY_ELIGIBLE|EARLY_ENTRY_ELIGIBLE|"
    r"EXIT TRIGGERED|EXIT_TRIGGERED)\b"
)
EXPECTED_REASONS = (
    "MARKET_CLOSED",
    "SESSION_CUTOFF",
    "SPOT_FEED_UNVERIFIED",
    "FEED_STALE",
    "ATR_UNAVAILABLE",
    "ZONE_ID_MISSING",
    "OPTION_CONTRACT_UNAVAILABLE",
    "OPTION_QUOTE_UNRELIABLE",
    "OPTION_COST_MODEL_UNAVAILABLE",
    "RISK_LIMIT_MISSING",
    "ENTRY_POLICY_DISABLED",
)
BANNED_KEYS = {
    "max_spread",
    "max_spread_ratio",
    "quote_age_ms",
    "slippage",
    "fee",
    "stt",
    "brokerage",
    "max_loss",
}


def _keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _keys(item)


class ClosedSessionTests(unittest.TestCase):
    def test_three_friday_closes(self):
        closes = load_closes()
        self.assertEqual(
            [(c.instrument, c.close_text, c.instrument_key) for c in closes],
            [
                ("NIFTY 50", "25144.3", "NSE_INDEX|Nifty 50"),
                ("BANKNIFTY", "61034.1", "NSE_INDEX|Nifty Bank"),
                ("SENSEX", "81592.45", "BSE_INDEX|SENSEX"),
            ],
        )
        self.assertEqual(closes[0].close, Decimal("25144.3"))
        self.assertEqual(closes[1].close, Decimal("61034.1"))
        self.assertEqual(closes[2].close, Decimal("81592.45"))
        self.assertEqual(closes[0].exchange_timestamp.weekday(), 4)
        self.assertEqual(STAGE_ASSESSMENT.weekday(), 6)

    def test_exchange_clock_is_not_the_saturday_api_clock(self):
        closes = load_closes()
        nifty_ms = unix_ms(datetime(2026, 11, 13, 10, 30, tzinfo=timezone.utc))
        sensex_ms = unix_ms(datetime(2026, 11, 13, 10, 29, 59, 508000, tzinfo=timezone.utc))
        self.assertEqual(closes[0].exchange_timestamp_ms, nifty_ms)
        self.assertEqual(closes[1].exchange_timestamp_ms, nifty_ms)
        self.assertEqual(closes[2].exchange_timestamp_ms, sensex_ms)
        self.assertEqual(nifty_ms - sensex_ms, 492)
        for close in closes:
            self.assertTrue(close.exchange_timestamp_text.startswith("2026-11-13"))
            self.assertEqual(close.audit_api_clock_text, "2026-11-14T19:54:57+05:30")
            self.assertNotEqual(close.exchange_timestamp_text, close.audit_api_clock_text)
            self.assertLess(close.exchange_timestamp, close.audit_api_clock)

    def test_sunday_afternoon_inside_cash_hours_is_still_closed(self):
        # 13:04 IST is inside 09:15–15:30, and the date is Sunday.
        self.assertTrue(outside_regular_session(STAGE_ASSESSMENT))
        self.assertLess(STAGE_ASSESSMENT.timetz().replace(tzinfo=None), datetime.strptime("15:00", "%H:%M").time())

    def test_snapshot_marks_and_plan_row(self):
        snapshots = build_closed_snapshots()
        self.assertEqual([s.snapshot_seq for s in snapshots], [1, 2, 3])
        prices = set()
        hashes = set()
        for snapshot in snapshots:
            plain = to_plain(snapshot)
            self.assertIsInstance(plain, dict)
            self.assertEqual(snapshot.content_hash, payload_hash(plain))
            self.assertEqual(snapshot.assessment, "CLOSED/HISTORICAL")
            self.assertEqual(snapshot.feed_quality, "DATA_STALE")
            self.assertEqual(snapshot.epoch, "CLOSED_HISTORICAL")
            self.assertEqual(snapshot.session_state, "CLOSED")
            self.assertEqual(snapshot.quality_flags, ("CLOSED/HISTORICAL", "DATA_STALE"))
            self.assertFalse(snapshot.entry_eligible)
            self.assertEqual(snapshot.entry_policy, "ENTRY_POLICY_DISABLED")
            self.assertEqual(snapshot.order_intent, "NONE")
            self.assertIsNone(snapshot.episode_id)
            self.assertIsNone(snapshot.virtual_trade_id)
            self.assertIsNone(snapshot.received_at)
            self.assertIsNone(snapshot.header.last_valid_tick)
            self.assertEqual(snapshot.header.last_exchange_print_kind, "SESSION_CLOSE")
            self.assertEqual(snapshot.header.exchange_date, "2026-11-13")
            self.assertEqual(snapshot.header.source_quality, "DATA_STALE")
            self.assertEqual(snapshot.header.last_engine_assessment, "CLOSED/HISTORICAL")
            self.assertEqual(snapshot.chart_timeframe, "3m")
            self.assertEqual(snapshot.chart_bars, ())
            self.assertEqual(snapshot.chart_overlays, ())
            self.assertEqual(snapshot.zone_ids_and_versions, ())
            self.assertEqual(snapshot.ranked_contracts, ())
            self.assertEqual(snapshot.structure_label, "UNDETERMINED")
            self.assertIsNone(snapshot.targets.t1)
            self.assertIsNone(snapshot.targets.t2)
            self.assertIsNone(snapshot.targets.t3)
            self.assertEqual(snapshot.depth_levels, 0)
            self.assertIsNone(snapshot.depth_rejection)
            self.assertFalse(snapshot.limits.production_complete)
            self.assertEqual(snapshot.limits.stage_a_live_windows, "DEFERRED")
            self.assertEqual(snapshot.limits.setup_b, "OUT_OF_SCOPE")
            self.assertEqual(snapshot.limits.d16, "OPEN")
            self.assertFalse(snapshot.limits.public_route_authorized)
            self.assertEqual(snapshot.limits.spot_feed, "UNVERIFIED")
            self.assertEqual(snapshot.reject_reasons, EXPECTED_REASONS)
            self.assertEqual(snapshot.highlighted_reject_reason, "MARKET_CLOSED")
            self.assertEqual(snapshot.five_rows[4].text, "NO VALID TRADE")
            self.assertEqual(snapshot.five_rows[4].detail, "MARKET_CLOSED")
            self.assertEqual(snapshot.five_rows[4].primary_reject_reason, "MARKET_CLOSED")
            self.assertEqual(snapshot.five_rows[3].text, "DATA_STALE")
            self.assertEqual(tuple(row.title for row in snapshot.five_rows), ROW_TITLES)
            for row in snapshot.five_rows:
                self.assertEqual(row.assessment, "CLOSED/HISTORICAL")
                self.assertEqual(row.feed_quality, "DATA_STALE")
            self.assertNotIn("FEED_DEGRADED", snapshot.reject_reasons)
            self.assertNotIn("UNKNOWN_SAFETY_STATE", snapshot.reject_reasons)
            self.assertEqual(
                snapshot.reject_reasons,
                tuple(r for r in REJECTION_PRECEDENCE if r in snapshot.reject_reasons),
            )
            encoded = json.dumps(plain)
            self.assertIsNone(BANNED_TEXT.search(encoded))
            self.assertFalse(BANNED_KEYS.intersection(_keys(plain)))
            self.assertEqual(snapshot.known_at, "2026-11-15T13:04:00+05:30")
            self.assertGreater(snapshot.known_at_ms, snapshot.exchange_timestamp_ms)
            self.assertNotEqual(snapshot.exchange_timestamp, snapshot.audit_api_clock)
            prices.add(snapshot.header.price)
            hashes.add(snapshot.content_hash)
            with self.assertRaises(Exception):
                snapshot.entry_eligible = True  # type: ignore[misc]
        self.assertEqual(prices, {"25144.3", "61034.1", "81592.45"})
        self.assertEqual(len(hashes), 3)
        again = build_closed_snapshots()
        self.assertEqual(
            [s.content_hash for s in snapshots],
            [s.content_hash for s in again],
        )

    def test_later_weekday_morning_does_not_promote_the_close(self):
        monday = datetime(2026, 11, 16, 10, 0, tzinfo=IST)
        self.assertEqual(monday.weekday(), 0)
        self.assertFalse(outside_regular_session(monday))
        snapshot = build_closed_snapshot(load_closes()[0], 1, monday)
        self.assertEqual(snapshot.assessment, "CLOSED/HISTORICAL")
        self.assertEqual(snapshot.feed_quality, "DATA_STALE")
        self.assertFalse(snapshot.entry_eligible)
        self.assertIn("MARKET_CLOSED", snapshot.reject_reasons)
        self.assertIn("FEED_STALE", snapshot.reject_reasons)
        self.assertIn("ENTRY_POLICY_DISABLED", snapshot.reject_reasons)
        self.assertEqual(snapshot.five_rows[4].text, "NO VALID TRADE")

    def test_print_time_itself_stays_historical(self):
        close = load_closes()[0]
        snapshot = build_closed_snapshot(close, 1, close.exchange_timestamp)
        self.assertEqual(snapshot.feed_quality, "DATA_STALE")
        self.assertEqual(snapshot.highlighted_reject_reason, "MARKET_CLOSED")
        self.assertIn("SESSION_CUTOFF", snapshot.reject_reasons)
        self.assertFalse(snapshot.entry_eligible)

    def test_assessment_cannot_precede_the_print(self):
        close = load_closes()[2]
        earlier = close.exchange_timestamp - timedelta(seconds=1)
        with self.assertRaises(ValueError):
            build_closed_snapshot(close, 1, earlier)

    def test_fixture_rejects_a_verified_label(self):
        payload = json.loads((PACKAGE / "fixtures" / "friday_13_nov_2026_closes.json").read_text())
        payload["closes"][0]["quality"] = "LIVE_VERIFIED"
        target = PACKAGE / "fixtures" / "_rejected_close.json"
        target.write_text(json.dumps(payload), encoding="utf-8")
        try:
            with self.assertRaises(ValueError):
                load_closes(target)
        finally:
            target.unlink()

    def test_build_does_not_open_a_socket(self):
        def boom(*_args, **_kwargs):
            raise AssertionError("socket opened")

        with patch.object(socket, "socket", boom), patch.object(socket, "create_connection", boom):
            built = build_closed_snapshots()
        self.assertEqual(len(built), 3)

    def test_product_modules_do_not_import_a_client_or_the_server(self):
        product = [
            PACKAGE / "closes.py",
            PACKAGE / "gaps.py",
            PACKAGE / "snapshot.py",
            PACKAGE / "__init__.py",
            PACKAGE / "__main__.py",
            PACKAGE / "reference" / "shivai_core.py",
        ]
        forbidden = {
            "fastapi",
            "uvicorn",
            "kiteconnect",
            "requests",
            "httpx",
            "aiohttp",
            "urllib",
            "socket",
            "websocket",
            "websockets",
            "paramiko",
            "subprocess",
        }
        banned_calls = {"write_text", "write_bytes", "mkdir", "unlink"}
        for path in product:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        self.assertNotIn(root, forbidden, path.name)
                elif isinstance(node, ast.ImportFrom):
                    root = (node.module or "").split(".")[0]
                    self.assertNotIn(root, forbidden, path.name)
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotEqual(node.func.id, "open", path.name)
                elif isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, banned_calls, path.name)
        for name in ("main.py", "strategy.py", "state.py"):
            for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
                self.assertNotIn("shivai", line.lower(), name)


if __name__ == "__main__":
    unittest.main()
