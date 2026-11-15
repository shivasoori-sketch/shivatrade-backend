import unittest
from decimal import Decimal as D
from shivai_core import (Bar, Zone, BreakoutEpisode, EpisodeState, Quality,
                         OptionQuote, VirtualTrade, option_quote_rejection,
                         research_snapshot, StrikeObservation, rank_research_strikes)


class CoreTests(unittest.TestCase):
    def base(self):
        e = BreakoutEpisode(Zone("N-R-01", 1, "NIFTY", D("25200"), "RESISTANCE", 100), D("40"))
        e.observed_cross(D("25201"), 101, Quality.LIVE_VERIFIED)
        e.completed_3m(Bar("NIFTY", 180, 180000, D("25210"), 180010))
        return e

    def test_no_degraded_cross(self):
        e = BreakoutEpisode(Zone("z", 1, "NIFTY", D("100"), "RESISTANCE", 1), D("10"))
        e.observed_cross(D("110"), 2, Quality.DEGRADED)
        self.assertEqual(e.state, EpisodeState.WATCH)

    def test_exact_atr_breakout_and_confirm(self):
        e = self.base()
        self.assertEqual(e.state, EpisodeState.ACCEPTANCE_PENDING)
        e.completed_1m(Bar("NIFTY", 60, 240000, D("25205"), 240010))
        self.assertEqual(e.state, EpisodeState.ACCEPTANCE_PENDING)
        e.completed_1m(Bar("NIFTY", 60, 300000, D("25203"), 300010))
        self.assertEqual(e.state, EpisodeState.BREAKOUT_CONFIRMED_RESEARCH)
        self.assertFalse(research_snapshot(5, e, Quality.LIVE_VERIFIED)["entry_eligible"])

    def test_reentry_fails(self):
        e = self.base()
        e.completed_1m(Bar("NIFTY", 60, 240000, D("25199"), 240010))
        self.assertEqual(e.reason, "REENTERED_RANGE")

    def test_missing_minute_fails(self):
        e = self.base()
        e.completed_1m(Bar("NIFTY", 60, 300000, D("25205"), 300010))
        self.assertEqual(e.reason, "CONFIRMATION_TIMEOUT")

    def test_deadline(self):
        e = self.base()
        e.check_deadline(360000)
        self.assertEqual(e.state, EpisodeState.EXPIRED)

    def test_option_missing_bid(self):
        q = OptionQuote("CE", D("0"), D("150"), 100, 100000, 100, 100)
        self.assertEqual(option_quote_rejection(q, 150, 1000, D("0.03")), "OPTION_QUOTE_UNRELIABLE")

    def test_virtual_stop_is_immutable(self):
        t = VirtualTrade("t1", "CE", D("150"), 100, D("135"), D("195"))
        stop = OptionQuote("CE", D("130"), D("133"), 200, 10000, 50, 50)
        t2 = t.evaluate(stop)
        self.assertEqual(t2.status, "STOP")
        recovery = OptionQuote("CE", D("250"), D("252"), 300, 10000, 50, 50)
        self.assertEqual(t2.evaluate(recovery).status, "STOP")

    def test_ranking_excludes_bad_quotes(self):
        a = StrikeObservation(OptionQuote("A", D("100"), D("101"), 100, 10000, 10, 10), D(".10"), D("2"), None, None)
        b = StrikeObservation(OptionQuote("B", D("0"), D("105"), 100, 10000, 10, 10), D(".20"), D("3"), None, None)
        self.assertEqual(rank_research_strikes([a, b], 110, 1000, D(".03"))[0][0], "A")


if __name__ == "__main__":
    unittest.main()
