"""Tests for reports/charts.json: candles per ticker for dashboard and HTML charts."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from src import report as report_module
from src.config import load_settings
from src.signal_engine import CHART_CANDLES, _chart_candles, analyze_ticker
from tests.test_pipeline import _intraday_turning_up, _synthetic_daily


def _analysis():
    settings = load_settings()
    analysis = replace(settings.analysis, proximity_threshold_pct=10.0, require_daily_close_reversal=False)
    risk = replace(settings.risk, min_net_crv=0.1, a_setup_net_crv=1.0)
    daily = _synthetic_daily()
    with mock.patch("src.signal_engine.fetch_daily", return_value=daily), \
         mock.patch("src.signal_engine.fetch_intraday", return_value=_intraday_turning_up()), \
         mock.patch("src.signal_engine.resample_to_4h", side_effect=lambda df: df), \
         mock.patch("src.signal_engine.get_upcoming_events", return_value=[]), \
         mock.patch("src.signal_engine.get_currency", return_value="EUR"):
        return analyze_ticker("TEST", analysis, risk, display_name="Test", min_confirmations=0), risk, analysis, daily


class ChartCandlesTest(unittest.TestCase):
    def test_keeps_the_last_bars_in_order(self):
        daily = _synthetic_daily()
        candles = _chart_candles(daily)
        self.assertEqual(len(candles), CHART_CANDLES)
        self.assertEqual(candles[-1]["t"], daily.index[-1].date().isoformat())
        self.assertEqual(list(candles[0]), ["t", "o", "h", "l", "c"])
        self.assertLess(candles[0]["t"], candles[-1]["t"])

    def test_short_history_returns_everything(self):
        self.assertEqual(len(_chart_candles(_synthetic_daily(n=20))), 20)

    def test_values_are_plain_rounded_floats(self):
        candle = _chart_candles(_synthetic_daily())[-1]
        self.assertIsInstance(candle["c"], float)
        self.assertEqual(candle["h"] - candle["c"], 1.0)


class ChartsFileTest(unittest.TestCase):
    def test_analysis_carries_candles(self):
        a, *_ = _analysis()
        self.assertEqual(len(a.candles), CHART_CANDLES)

    def test_build_charts_is_keyed_by_ticker(self):
        a, *_ = _analysis()
        charts = report_module.build_charts([a], "2026-10-19T20:00:00+00:00")
        self.assertEqual(charts["schema_version"], report_module.CHARTS_SCHEMA_VERSION)
        self.assertEqual(charts["charts"]["TEST"]["currency"], "EUR")
        self.assertEqual(len(charts["charts"]["TEST"]["candles"]), CHART_CANDLES)

    def test_write_reports_writes_charts_but_not_into_latest(self):
        a, risk, analysis, _ = _analysis()
        report = report_module.build_report([a], {}, 10.0, risk, analysis)
        charts = report_module.build_charts([a], report["generated_at_utc"])
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(report_module, "REPORTS_DIR", Path(tmp) / "reports"), \
             mock.patch.object(report_module, "SITE_DIR", Path(tmp) / "site"):
            report_module.write_reports(report, charts)
            written = json.loads((Path(tmp) / "reports" / "charts.json").read_text(encoding="utf-8"))
            latest = json.loads((Path(tmp) / "reports" / "latest.json").read_text(encoding="utf-8"))
        self.assertEqual(written["charts"]["TEST"]["candles"][-1], charts["charts"]["TEST"]["candles"][-1])
        self.assertNotIn("candles", json.dumps(latest))

    def test_write_reports_without_charts_leaves_no_file(self):
        a, risk, analysis, _ = _analysis()
        report = report_module.build_report([a], {}, 10.0, risk, analysis)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(report_module, "REPORTS_DIR", Path(tmp) / "reports"), \
             mock.patch.object(report_module, "SITE_DIR", Path(tmp) / "site"):
            report_module.write_reports(report)
            self.assertFalse((Path(tmp) / "reports" / "charts.json").exists())


if __name__ == "__main__":
    unittest.main()
