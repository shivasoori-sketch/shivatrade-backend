"""The Monday handoff keeps Friday until a later completed session exists."""
from __future__ import annotations

import unittest
from pathlib import Path

from shivai_r3.refresh_session import (
    KEYS,
    latest_shared_date,
    plan,
    rows_on_date,
    session_is_complete,
)

PACKAGE = Path(__file__).resolve().parents[1]


class RefreshPlanTests(unittest.TestCase):
    def test_friday_stays_until_a_later_completed_session(self):
        self.assertEqual(plan("2026-11-13", "2026-11-13", True), "keep")
        self.assertEqual(plan("2026-11-13", "2026-11-16", False), "keep")
        self.assertEqual(plan("2026-11-13", "2026-11-16", True), "replace")

    def test_latest_date_must_be_shared_and_complete(self):
        early = ["2026-11-16T09:15:00+05:30", "1", "1", "1", "1", "0", "0"]
        done = ["2026-11-16T15:27:00+05:30", "1", "1", "1", "1", "0", "0"]
        friday = ["2026-11-13T15:27:00+05:30", "1", "1", "1", "1", "0", "0"]
        series = {key: [friday, early, done] for key in KEYS}
        self.assertEqual(latest_shared_date(series), "2026-11-16")
        day = rows_on_date(series[KEYS[0]], "2026-11-16")
        self.assertEqual(len(day), 2)
        self.assertTrue(session_is_complete(day))
        self.assertFalse(session_is_complete([early]))

    def test_indexes_that_disagree_are_rejected(self):
        series = {key: [["2026-11-16T15:27:00+05:30"]] for key in KEYS}
        series[KEYS[2]] = [["2026-11-13T15:27:00+05:30"]]
        with self.assertRaises(ValueError):
            latest_shared_date(series)

    def test_refresh_does_not_open_a_live_socket(self):
        source = (PACKAGE / "refresh_session.py").read_text(encoding="utf-8")
        self.assertNotIn("websocket", source.lower())
        self.assertNotIn("wss://", source)
        page = (PACKAGE / "page.py").read_text(encoding="utf-8")
        self.assertNotIn("refresh_session", page)


if __name__ == "__main__":
    unittest.main()
