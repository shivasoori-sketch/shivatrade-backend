"""REST quote header over the stored Friday candles. No network."""
from __future__ import annotations

import unittest

from shivai_r3.page import render_closes, render_degraded
from shivai_r3.snapshot import RestQuote, close_views, degraded_rest_views

QUOTES = {
    "NSE_INDEX|Nifty 50": RestQuote("26001.5", "2026-11-16T15:02:00+05:30", "2026-11-16T15:01:58+05:30", "2s"),
    "NSE_INDEX|Nifty Bank": RestQuote("62002.5", "2026-11-16T15:02:00+05:30", "2026-11-16T15:01:58+05:30", "2s"),
    "BSE_INDEX|SENSEX": RestQuote("83003.5", "2026-11-16T15:02:00+05:30", "2026-11-16T15:01:57+05:30", "3s"),
}


class DegradedRestTests(unittest.TestCase):
    def test_quote_does_not_become_a_candle(self):
        friday = close_views()
        views = degraded_rest_views(QUOTES)
        self.assertEqual([view.instrument for view in views], ["NIFTY", "BANKNIFTY", "SENSEX"])
        for view, stored in zip(views, friday, strict=True):
            self.assertEqual(view.three_minute_bars, stored.three_minute_bars)
            self.assertEqual(len(view.three_minute_bars), 125)
            self.assertEqual(view.three_minute_bars[-1].time_ist, "2026-11-13T15:27:00+05:30")
            self.assertNotEqual(view.price, view.three_minute_bars[-1].close)
            self.assertEqual(view.source, "UPSTOX REST")
            self.assertEqual(view.source_quality, "DEGRADED")
            self.assertFalse(view.entry_eligible)
            self.assertEqual(view.reject_reasons, ("ENTRY_POLICY_DISABLED",))
            self.assertEqual(
                tuple(row.value for row in view.five_rows),
                ("UNDETERMINED", "RESEARCH_ONLY", "RESEARCH_ONLY", "RESEARCH_ONLY", "NO_VALID_TRADE"),
            )

    def test_page_shows_the_quote_and_the_friday_chart(self):
        page = render_degraded(QUOTES)
        self.assertIn(">UPSTOX REST<", page)
        self.assertIn(">DEGRADED<", page)
        self.assertIn(">false<", page)
        self.assertIn(">ENTRY_POLICY_DISABLED<", page)
        self.assertIn("Friday 13 Nov 2026 session", page)
        self.assertIn("the quote is not a candle", page)
        self.assertIn("26001.5", page)
        self.assertIn("62002.5", page)
        self.assertIn("83003.5", page)
        self.assertEqual(page.count('"time":'), 375)
        self.assertIn("2026-11-13", page)
        self.assertIn("09:15-15:27 IST", page)
        self.assertNotIn("3-minute spot", page)
        self.assertNotIn("LIVE VERIFIED", page)
        self.assertNotIn("LIVE_VERIFIED", page)
        closes = render_closes()
        self.assertIn("3-minute spot", closes)
        self.assertNotIn("ENTRY_POLICY_DISABLED", closes)


if __name__ == "__main__":
    unittest.main()
