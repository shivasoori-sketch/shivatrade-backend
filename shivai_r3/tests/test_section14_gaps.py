"""Section 14 gaps stay incomplete. These tapes are not a production engine."""
from __future__ import annotations

import ast
import json
import unittest
from decimal import Decimal
from pathlib import Path

from shivai_r3.gaps import (
    D16,
    GAPS,
    PUBLIC_ROUTE_AUTHORIZED,
    SETUP_B,
    STAGE_A_LIVE_WINDOWS,
    SWING_EVENT_FIXTURES_REQUIRED,
    atr14_15m_prior,
    index_depth_rejection,
    order_book_flow,
    persist_snapshot,
    project_premium_targets,
    structure_from_bars,
    swing_event_fixture_count,
)
from shivai_r3.reference.shivai_core import OptionQuote, VirtualTrade
from shivai_r3.snapshot import close_views

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "section14_incomplete.json"
EXPECTED_GAPS = (
    ("production_upstox_transport", "NOT_IMPLEMENTED"),
    ("bos_choch_detector", "NOT_IMPLEMENTED"),
    ("atr_computation", "NOT_IMPLEMENTED"),
    ("order_book_flow", "NOT_IMPLEMENTED"),
    ("option_premium_projection", "NOT_IMPLEMENTED"),
    ("risk_fee_model", "NOT_IMPLEMENTED"),
    ("trade_guardian", "REFERENCE_SUBSET_ONLY"),
    ("authenticated_live_ui", "NOT_BUILT"),
    ("storage", "NOT_IMPLEMENTED"),
    ("public_deployment", "NOT_AUTHORIZED"),
)


class Section14GapTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_gap_catalog_matches_section_14(self):
        self.assertEqual([(gap.gap_id, gap.status) for gap in GAPS], list(EXPECTED_GAPS))
        self.assertEqual(swing_event_fixture_count(), 0)
        self.assertEqual(self.fixture["swing_event_fixtures_required"], SWING_EVENT_FIXTURES_REQUIRED)
        self.assertLess(swing_event_fixture_count(), SWING_EVENT_FIXTURES_REQUIRED)
        swing_files = list(FIXTURE.parent.glob("*swing*"))
        self.assertEqual(swing_files, [])
        self.assertEqual(STAGE_A_LIVE_WINDOWS, "DEFERRED")
        self.assertEqual(SETUP_B, "OUT_OF_SCOPE")
        self.assertEqual(D16, "OPEN")
        self.assertFalse(PUBLIC_ROUTE_AUTHORIZED)

    def test_bos_tape_stays_undetermined(self):
        tape = self.fixture["bos_tape"]
        read = structure_from_bars(tape["bars"])
        self.assertEqual(read.label, tape["expected_structure"])
        self.assertEqual(list(read.zone_ids), tape["expected_zone_ids"])
        self.assertFalse(read.implemented)
        for view in close_views():
            self.assertEqual(view.chart_overlays, ())
            self.assertFalse(view.entry_eligible)
            self.assertEqual(view.five_rows[0].value, "UNDETERMINED")

    def test_twenty_prior_bars_do_not_produce_atr(self):
        tape = self.fixture["atr_tape"]
        bars = [
            {"timeframe_s": tape["timeframe_s"], "end_ms": (index + 1) * tape["timeframe_s"] * 1000, "close": str(100 + index)}
            for index in range(tape["bar_count"])
        ]
        self.assertEqual(len(bars), 20)
        self.assertIsNone(atr14_15m_prior(bars))
        self.assertIsNone(atr14_15m_prior(()))
        self.assertIsNone(tape["expected_atr"])
        for view in close_views():
            self.assertNotIn("ATR_UNAVAILABLE", view.reject_reasons)

    def test_order_book_depth_is_not_a_rejection_and_flow_is_absent(self):
        for case in self.fixture["order_book_cases"]:
            self.assertEqual(index_depth_rejection(case["depth_levels"]), case["expected_rejection"])
            self.assertEqual(order_book_flow(), case["expected_flow"])
        for view in close_views():
            self.assertNotIn("DEPTH", " ".join(view.reject_reasons))

    def test_premium_targets_are_not_projected(self):
        targets = project_premium_targets()
        expected = self.fixture["premium"]
        self.assertEqual(targets.t1, expected["t1"])
        self.assertEqual(targets.t2, expected["t2"])
        self.assertEqual(targets.t3, expected["t3"])
        self.assertIsNone(targets.t1)

    def test_risk_and_fee_model_stay_open(self):
        self.assertEqual(D16, "OPEN")
        for view in close_views():
            self.assertEqual(view.reject_reasons, ("ENTRY_POLICY_DISABLED",))
            self.assertEqual(view.five_rows[2].value, "")

    def test_guardian_does_not_open_and_reference_stop_sticks(self):
        for view in close_views():
            self.assertEqual(view.five_rows[3].value, "RESEARCH_ONLY")
            encoded = " ".join(row.value for row in view.five_rows)
            for state in ("VIRTUAL_OPEN", "HOLD", "CAUTION", "PROTECT", "COMPLETE", "EXIT_TRIGGERED"):
                self.assertNotIn(state, encoded)
        trade = VirtualTrade("t1", "CE", Decimal("150"), 100, Decimal("135"), Decimal("195"))
        stopped = trade.evaluate(OptionQuote("CE", Decimal("130"), Decimal("133"), 200, 10000, 50, 50))
        self.assertEqual(stopped.status, "STOP")
        recovered = stopped.evaluate(OptionQuote("CE", Decimal("250"), Decimal("252"), 300, 10000, 50, 50))
        self.assertEqual(recovered.status, "STOP")
        self.assertEqual(trade.status, "OPEN")

    def test_storage_and_route_are_not_created(self):
        destination = FIXTURE.parent / "_should_not_exist.json"
        status = persist_snapshot({"snapshot_seq": 1}, destination)
        self.assertEqual(status, "NOT_IMPLEMENTED")
        self.assertFalse(destination.exists())
        self.assertFalse(PUBLIC_ROUTE_AUTHORIZED)
        package = Path(__file__).resolve().parents[1]
        names = {path.name for path in package.rglob("*") if path.is_file()}
        self.assertFalse(any(name.endswith((".html", ".js", ".css")) for name in names))

    def test_package_has_no_server_entrypoint(self):
        tree = ast.parse((Path(__file__).resolve().parents[1] / "__init__.py").read_text())
        self.assertFalse(any(isinstance(node, ast.FunctionDef) and node.name == "app" for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
