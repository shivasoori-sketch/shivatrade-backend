"""F-C01 recording rules. No socket and no token."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import unittest

from shivai_r3.fc01_capture import (
    KEYS,
    IndexCapture,
    cash_session_open,
    feed_checkpoint,
    observations_from_decoded,
    redact,
    summary_document,
)

IST = ZoneInfo("Asia/Kolkata")
PACKAGE = Path(__file__).resolve().parents[1]


class Fc01CaptureTests(unittest.TestCase):
    def test_sunday_is_closed_and_a_quiet_socket_is_not_a_pass(self):
        sunday = datetime(2026, 11, 15, 14, 0, tzinfo=IST)
        self.assertFalse(cash_session_open(sunday))
        indexes = {key: IndexCapture() for key in KEYS}
        document = summary_document(
            indexes,
            authorize_status=200,
            disconnects=1,
            decode_failures=0,
            duration_sec=25,
            dry_run=True,
            session_open=False,
            reason="closed_session",
        )
        self.assertFalse(document["pass"])
        self.assertFalse(document["data_available"])
        self.assertFalse(document["data_validated"])
        self.assertFalse(document["signal_eligible"])
        self.assertFalse(document["entry_eligible"])
        self.assertTrue(document["connection_alone_is_not_a_pass"])
        for key in KEYS:
            self.assertEqual(document["indexes"][key]["feed_checkpoint"], "not_a_pass")

    def test_exchange_time_stays_separate_from_receipt_time(self):
        rows = observations_from_decoded(
            {
                "type": "live_feed",
                "currentTs": "1794565800000",
                "feeds": {
                    "NSE_INDEX|Nifty 50": {"ltpc": {"ltp": 25144.3, "ltt": "1794565800000"}},
                },
            },
            "2026-11-15T14:00:00+00:00",
        )
        self.assertEqual(rows[0]["exchange_timestamp_ms"], 1794565800000)
        self.assertEqual(rows[0]["received_at_utc"], "2026-11-15T14:00:00+00:00")
        self.assertNotEqual(rows[0]["exchange_timestamp_ms"], rows[0]["received_at_utc"])
        self.assertTrue(rows[0]["exchange_timestamp_present"])
        index = IndexCapture()
        index.note(1794565800000, rows[0]["received_at_utc"])
        index.note(1794565800000, rows[0]["received_at_utc"])
        index.note(1794565800000 + 6000, rows[0]["received_at_utc"])
        self.assertEqual(index.duplicate_count, 1)
        self.assertEqual(len(index.gaps), 1)
        self.assertEqual(index.gaps[0]["delta_ms"], 6000)

    def test_missing_exchange_timestamp_is_recorded_absent(self):
        rows = observations_from_decoded(
            {"type": "live_feed", "feeds": {"NSE_INDEX|Nifty 50": {"ltpc": {"ltp": 1}}}},
            "2026-11-16T04:00:00+00:00",
        )
        self.assertFalse(rows[0]["exchange_timestamp_present"])
        index = IndexCapture()
        index.subscription_ack = True
        index.note(None, rows[0]["received_at_utc"])
        self.assertEqual(
            feed_checkpoint(index, duration_sec=600, dry_run=False, session_open=True),
            "fail",
        )

    def test_summary_cannot_carry_a_token(self):
        secret = "super-secret-token-value"
        self.assertEqual(redact(f"Bearer {secret} wss://example", [secret]), "Bearer [redacted] wss://example")
        source = (PACKAGE / "fc01_capture.py").read_text(encoding="utf-8")
        self.assertNotIn("brokers.json", source)
        self.assertNotIn("DATA_VALIDATED = True", source)
        self.assertNotIn("SIGNAL_ELIGIBLE = True", source)


if __name__ == "__main__":
    unittest.main()
