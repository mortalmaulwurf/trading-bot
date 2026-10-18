"""Tests for the versioned JSON report contract consumed by dashboards."""
import unittest
from dataclasses import replace
from unittest import mock

from src import report as report_module
from src.config import load_settings
from src.signal_engine import analyze_ticker
from tests.test_pipeline import _intraday_turning_up, _synthetic_daily


class ReportContractTest(unittest.TestCase):
    def setUp(self):
        settings = load_settings()
        self.analysis = replace(settings.analysis, proximity_threshold_pct=10.0, require_daily_close_reversal=False)
        self.risk = replace(settings.risk, min_net_crv=0.1, a_setup_net_crv=1.0)

    def _result(self):
        daily = _synthetic_daily()
        with mock.patch("src.signal_engine.fetch_daily", return_value=daily), \
             mock.patch("src.signal_engine.fetch_intraday", return_value=_intraday_turning_up()), \
             mock.patch("src.signal_engine.resample_to_4h", side_effect=lambda df: df), \
             mock.patch("src.signal_engine.get_upcoming_events", return_value=[]), \
             mock.patch("src.signal_engine.get_currency", return_value="EUR"):
            return analyze_ticker("TEST", self.analysis, self.risk, display_name="Test", min_confirmations=0)

    def test_schema_and_status(self):
        a = self._result()
        ok = report_module.build_report([a], {}, 10.0, self.risk, self.analysis)
        self.assertEqual(ok["schema_version"], report_module.REPORT_SCHEMA_VERSION)
        self.assertEqual(ok["status"], "ok")
        self.assertEqual(ok["rule_set"]["max_risk_per_trade_eur"], 10)
        self.assertIn("rule_checks", ok["all_results"][0])
        self.assertIn("profile_basis", ok["all_results"][0])
        partial = report_module.build_report([a], {"X": "boom"}, 10.0, self.risk, self.analysis)
        self.assertEqual(partial["status"], "partial")
        failed = report_module.build_report([], {"X": "boom"}, 10.0, self.risk, self.analysis)
        self.assertEqual(failed["status"], "failed")

    def test_build_report_without_analysis_settings_stays_compatible(self):
        a = self._result()
        report = report_module.build_report([a], {}, 10.0, self.risk)
        self.assertIsNone(report["rule_set"]["require_daily_close_reversal"])

    def test_markdown_shows_rule_check(self):
        a = self._result()
        report = report_module.build_report([a], {}, 10.0, self.risk, self.analysis)
        md = report_module._format_markdown(report)
        self.assertIn("Regel-Check", md)


if __name__ == "__main__":
    unittest.main()
