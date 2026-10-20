"""Tests for the display-only paper-trade tier (net CRV between paper_net_crv and min_net_crv)."""
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from unittest import mock

from src import report as report_module
from src.config import load_settings
from src.html_report import render_html
from src.signal_engine import analyze_ticker
from src.status import format_morning_message
from tests.test_pipeline import _intraday_turning_up, _synthetic_daily


class PaperTierTest(unittest.TestCase):
    def setUp(self):
        settings = load_settings()
        self.analysis = replace(settings.analysis, proximity_threshold_pct=10.0, require_daily_close_reversal=False)
        self.settings = settings

    def _report(self, min_crv: float, paper_crv: float) -> dict:
        risk = replace(self.settings.risk, min_net_crv=min_crv, paper_net_crv=paper_crv, a_setup_net_crv=min_crv + 1)
        with mock.patch("src.signal_engine.fetch_daily", return_value=_synthetic_daily()), \
             mock.patch("src.signal_engine.fetch_intraday", return_value=_intraday_turning_up()), \
             mock.patch("src.signal_engine.resample_to_4h", side_effect=lambda df: df), \
             mock.patch("src.signal_engine.get_upcoming_events", return_value=[]), \
             mock.patch("src.signal_engine.get_currency", return_value="EUR"):
            a = analyze_ticker("TEST", self.analysis, risk, display_name="Test", min_confirmations=0)
        self.assertIsNotNone(a.position_suggestion)
        self.crv = a.position_suggestion.net_crv
        return report_module.build_report([a], {}, 10.0, risk, self.analysis)

    def test_defaults_come_from_settings(self):
        risk = load_settings().risk
        self.assertEqual(risk.paper_net_crv, 2.0)
        self.assertLess(risk.paper_net_crv, risk.min_net_crv)

    def test_setup_between_thresholds_is_a_paper_trade(self):
        probe = self._report(min_crv=0.1, paper_crv=0.05)
        crv = probe["all_results"][0]["rule_checks"]["net_crv"]
        report = self._report(min_crv=crv + 1.0, paper_crv=crv - 0.01)
        item = report["all_results"][0]
        self.assertTrue(item["is_paper_trade"])
        self.assertFalse(item["is_actionable"])
        self.assertEqual(report["paper_trades_count"], 1)
        self.assertEqual(report["rule_set"]["paper_net_crv"], crv - 0.01)

    def test_below_paper_threshold_is_not_flagged(self):
        probe = self._report(min_crv=0.1, paper_crv=0.05)
        crv = probe["all_results"][0]["rule_checks"]["net_crv"]
        report = self._report(min_crv=crv + 2.0, paper_crv=crv + 1.0)
        self.assertFalse(report["all_results"][0]["is_paper_trade"])
        self.assertEqual(report["paper_trades_count"], 0)

    def test_actionable_setup_is_not_a_paper_trade(self):
        report = self._report(min_crv=0.1, paper_crv=0.05)
        item = report["all_results"][0]
        self.assertTrue(item["is_actionable"])
        self.assertFalse(item["is_paper_trade"])

    def test_html_badge_and_status_line(self):
        probe = self._report(min_crv=0.1, paper_crv=0.05)
        crv = probe["all_results"][0]["rule_checks"]["net_crv"]
        report = self._report(min_crv=crv + 1.0, paper_crv=crv - 0.01)
        html = render_html(report, {})
        self.assertIn("Papier-Trade ≥", html)
        text = format_morning_message(report, datetime.now(timezone.utc))
        self.assertIn("Papier-Trade: Test", text)
        self.assertNotIn("Treffer ohne Setup: Test", text)


if __name__ == "__main__":
    unittest.main()
