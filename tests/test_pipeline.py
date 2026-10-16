"""Offline end-to-end test: synthetic price data through analysis, report, HTML and Telegram text."""
import unittest
from dataclasses import replace
from unittest import mock

import numpy as np
import pandas as pd

from src import report as report_module
from src.config import AnalysisSettings, load_settings
from src.html_report import render_html
from src.notifier import format_alerts_message
from src.signal_engine import analyze_ticker


def _synthetic_daily(n: int = 200, last_volume_factor: float = 3.0) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=n, freq="B", tz="UTC")
    close = 100 + 5 * np.sin(np.linspace(0, 8 * np.pi, n))
    df = pd.DataFrame(
        {"Open": close, "High": close + 1.0, "Low": close - 1.0, "Close": close, "Volume": 1_000_000.0},
        index=idx,
    )
    df.iloc[-1, df.columns.get_loc("Volume")] *= last_volume_factor
    return df


def _intraday_turning_up() -> pd.DataFrame:
    idx = pd.date_range("2026-10-01", periods=12, freq="h", tz="UTC")
    close = np.array([10, 9, 8, 7, 8, 9, 10, 11, 12, 11.5, 11.8, 12.0], dtype=float)
    return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close, "Volume": 1.0}, index=idx)


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.settings = load_settings()
        self.analysis: AnalysisSettings = self.settings.analysis
        # Relax thresholds so the synthetic series produces a hit with a computable plan.
        self.analysis = replace(self.analysis, proximity_threshold_pct=10.0)
        self.risk = replace(self.settings.risk, min_net_crv=0.1, a_setup_net_crv=1.0)

    def _analyze(self, **kwargs):
        daily = _synthetic_daily()
        with mock.patch("src.signal_engine.fetch_daily", return_value=daily), \
             mock.patch("src.signal_engine.fetch_intraday", return_value=_intraday_turning_up()), \
             mock.patch("src.signal_engine.resample_to_4h", side_effect=lambda df: df), \
             mock.patch("src.signal_engine.get_upcoming_events", return_value=[]), \
             mock.patch("src.signal_engine.get_currency", return_value="EUR"), \
             mock.patch("src.signal_engine.fetch_index_ratio", return_value=120.0):
            return analyze_ticker("TEST", self.analysis, self.risk, display_name="Test", **kwargs)

    def test_hit_gets_plan_and_alert(self):
        a = self._analyze(index_symbol="^TEST", min_confirmations=2)
        self.assertTrue(a.is_hit)
        self.assertGreaterEqual(a.confirmations, 2)  # volume spike + intraday momentum
        self.assertIsNotNone(a.position_suggestion)
        self.assertIsNotNone(a.target_name)
        self.assertGreater(a.position_suggestion.stop_distance_pct, 0)
        self.assertLessEqual(a.position_suggestion.total_loss_eur, self.risk.max_risk_per_trade_eur + 1e-6)
        self.assertTrue(a.is_actionable)
        self.assertEqual(a.index_ratio, 120.0)

        report = report_module.build_report([a], {}, self.analysis.proximity_threshold_pct, self.risk)
        self.assertEqual(report["alerts_count"], 1)
        md = report_module._format_markdown(report)
        self.assertIn("Plan (Long)", md)
        self.assertIn("Indexwerte", md)
        self.assertNotIn("2er-Hebel", md)
        html = render_html(report)
        self.assertIn("Hebel", html)
        self.assertNotIn("2er-Hebel", html)
        msg = format_alerts_message(report, site_url="https://example.invalid")
        self.assertIn("Setup-Alarm", msg)
        self.assertIn("Netto-CRV", msg)

    def test_alert_is_gated_by_confirmations(self):
        a = self._analyze(min_confirmations=3)
        self.assertTrue(a.is_hit)
        self.assertFalse(a.is_actionable)

    def test_alert_is_gated_by_net_crv(self):
        self.risk = replace(self.risk, min_net_crv=1000.0)
        a = self._analyze(min_confirmations=2)
        self.assertTrue(a.is_hit)
        self.assertFalse(a.is_actionable)
        report = report_module.build_report([a], {}, self.analysis.proximity_threshold_pct, self.risk)
        self.assertEqual(report["alerts_count"], 0)
        self.assertEqual(report["hits_count"], 1)


if __name__ == "__main__":
    unittest.main()
