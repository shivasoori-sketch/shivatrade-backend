"""3-minute candles and the Tuesday page. No network."""
from __future__ import annotations

import json
import unittest
import uuid
from datetime import datetime
from decimal import Decimal

from shivai_r3.candles import (
    CandleBook,
    IST,
    as_decimal,
    is_full_cash_session,
    live_state,
    seed_book,
    waiting_state,
)
from shivai_r3.fc01_capture import KEYS, subscribe_frame
from shivai_r3.live_feed import phase
from shivai_r3.page import render_closes, render_live


def _ms(hour: int, minute: int, second: int = 0, day: int = 17) -> int:
    stamp = datetime(2026, 11, day, hour, minute, second, tzinfo=IST)
    return int(stamp.timestamp() * 1000)


class CandleTests(unittest.TestCase):
    def test_three_minutes_stay_one_candle(self):
        book = CandleBook(session_date=None)
        key = "NSE_INDEX|Nifty 50"
        book.add(key, _ms(9, 15, 0), "100")
        book.add(key, _ms(9, 17, 59), "110")
        book.add(key, _ms(9, 16, 10), "90")
        book.add(key, _ms(9, 18, 0), "95")
        rows = book.candles(key)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].start.strftime("%H:%M"), "09:15")
        self.assertEqual((rows[0].open, rows[0].high, rows[0].low, rows[0].close), (
            Decimal("100.00"), Decimal("110.00"), Decimal("90.00"), Decimal("90.00"),
        ))
        self.assertEqual(rows[1].start.strftime("%H:%M"), "09:18")
        self.assertEqual(rows[1].open, Decimal("95.00"))

    def test_a_tick_without_exchange_time_is_skipped(self):
        book = CandleBook()
        self.assertFalse(book.add("NSE_INDEX|Nifty 50", None, "100"))
        self.assertEqual(book.candles("NSE_INDEX|Nifty 50"), [])
        self.assertEqual(book.skipped, 1)

    def test_a_restart_keeps_tuesday_and_drops_another_day(self):
        source = CandleBook(session_date=None)
        key = "NSE_INDEX|Nifty 50"
        source.add(key, _ms(9, 15), "100")
        source.add(key, _ms(9, 16), "110")
        state = live_state(source, "live", "DEGRADED", {key: "110"})
        restored = CandleBook()
        prices = seed_book(restored, state)
        rows = restored.candles(key)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].open, Decimal("100.00"))
        self.assertEqual(rows[0].high, Decimal("110.00"))
        self.assertEqual(rows[0].close, Decimal("110.00"))
        self.assertEqual(prices[key], "110")
        other = live_state(CandleBook(session_date=None), "disconnected", "STALE")
        other["session_date"] = "2026-11-16"
        self.assertEqual(seed_book(CandleBook(), other), {})

    def test_tuesday_book_rejects_another_day(self):
        book = CandleBook()
        self.assertFalse(book.add("NSE_INDEX|Nifty 50", _ms(14, 50, day=16), "100"))
        self.assertEqual(book.candles("NSE_INDEX|Nifty 50"), [])

    def test_afternoon_capture_is_not_a_full_session(self):
        book = CandleBook(session_date=None)
        key = "NSE_INDEX|Nifty 50"
        book.add(key, _ms(14, 50, day=16), "100")
        book.add(key, _ms(15, 0, day=16), "101")
        rows = book.candles(key)
        self.assertFalse(is_full_cash_session(rows))
        self.assertNotEqual(rows[0].start.strftime("%H:%M"), "09:15")

    def test_float_text_keeps_the_index_decimals(self):
        self.assertEqual(as_decimal(25220.1), Decimal("25220.10"))
        state = live_state(CandleBook(), "live", "DEGRADED", {"NSE_INDEX|Nifty 50": "25220.1"})
        self.assertIn("25220.1", json.dumps(state))
        self.assertFalse(state["entry_eligible"])
        self.assertEqual(state["source_quality"], "DEGRADED")
        with self.assertRaises(ValueError):
            live_state(CandleBook(), "live", "LIVE_VERIFIED")


class PageTests(unittest.TestCase):
    def test_live_page_has_no_stored_session(self):
        page = render_live()
        self.assertIn(">UPSTOX WEBSOCKET<", page)
        self.assertIn(">STALE<", page)
        self.assertIn(">disconnected<", page)
        self.assertIn(">false<", page)
        self.assertIn(">ENTRY_POLICY_DISABLED<", page)
        self.assertIn(">UNDETERMINED<", page)
        self.assertIn(">NO_VALID_TRADE<", page)
        self.assertEqual(page.count(">RESEARCH_ONLY<"), 9)
        self.assertIn("Tuesday 17 Nov 2026 session", page)
        self.assertIn("/shivai?live=1", page)
        self.assertIn("A stored session is not drawn.", page)
        self.assertEqual(page.count('"bars":[]'), 3)
        self.assertNotIn("2026-11-13", page)
        self.assertNotIn("25144.3", page)
        self.assertNotIn("61034.1", page)
        self.assertNotIn("81592.45", page)
        self.assertNotIn("Friday", page)
        self.assertNotIn("3-minute spot", page)
        self.assertNotIn("LIVE_VERIFIED", page)
        self.assertNotIn("BOS", page)
        self.assertNotIn("CHoCH", page)
        closes = render_closes()
        self.assertIn("3-minute spot", closes)
        self.assertNotIn("ENTRY_POLICY_DISABLED", closes)

    def test_waiting_document_is_empty(self):
        state = waiting_state()
        self.assertEqual(state["session_date"], "2026-11-17")
        self.assertEqual(state["source"], "UPSTOX WEBSOCKET")
        self.assertEqual(state["feed"], "disconnected")
        self.assertEqual(state["source_quality"], "STALE")
        self.assertFalse(state["entry_eligible"])
        for name in ("NIFTY", "BANKNIFTY", "SENSEX"):
            self.assertEqual(state["indexes"][name]["candles"], [])
            self.assertEqual(state["indexes"][name]["price"], "")


class FeedWindowTests(unittest.TestCase):
    def test_the_socket_is_armed_only_for_tuesday(self):
        self.assertEqual(phase(datetime(2026, 11, 16, 15, 51, tzinfo=IST)), "exit")
        self.assertEqual(phase(datetime(2026, 11, 17, 9, 14, 30, tzinfo=IST)), "wait")
        self.assertEqual(phase(datetime(2026, 11, 17, 9, 15, tzinfo=IST)), "run")
        self.assertEqual(phase(datetime(2026, 11, 17, 15, 29, tzinfo=IST)), "run")
        self.assertEqual(phase(datetime(2026, 11, 17, 15, 30, tzinfo=IST)), "exit")
        self.assertEqual(phase(datetime(2026, 11, 18, 9, 15, tzinfo=IST)), "exit")

    def test_subscribe_frame_is_the_binary_one(self):
        frame = subscribe_frame(KEYS)
        self.assertIsInstance(frame, bytes)
        payload = json.loads(frame.decode("utf-8"))
        uuid.UUID(payload["guid"])
        self.assertEqual(payload["method"], "sub")
        self.assertEqual(payload["data"]["mode"], "ltpc")
        self.assertEqual(payload["data"]["instrumentKeys"], list(KEYS))


if __name__ == "__main__":
    unittest.main()
