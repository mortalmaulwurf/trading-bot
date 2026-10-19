"""Tests for the current rule set: 3:1 net CRV, daily-close reversal gate, anchored profile, JSON contract."""
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from src import indicators
from src.config import load_settings
from src.signal_engine import _select_profile_frame, analyze_ticker
from tests.test_pipeline import _intraday_turning_up, _synthetic_daily


def _frame(lows: list[float], closes: list[float], opens: list[float] | None = None) -> pd.DataFrame:
    idx = pd.date_range("2026-10-01", periods=len(closes), freq="B", tz="UTC")
    return pd.DataFrame(
        {
            "Open": opens if opens is not None else closes,
            "High": [c + 1 for c in closes],
            "Low": lows,
            "Close": closes,
            "Volume": [1.0] * len(closes),
        },
        index=idx,
    )


class DailyCloseReversalTest(unittest.TestCase):
    def test_tested_and_closed_above(self):
        df = _frame(lows=[105, 101, 99.8], closes=[106, 103, 101])
        self.assertTrue(indicators.daily_close_reversal(df, level=100.0, tolerance_pct=0.5, lookback_bars=3))

    def test_closed_below_level(self):
        df = _frame(lows=[105, 101, 98], closes=[106, 103, 99])
        self.assertFalse(indicators.daily_close_reversal(df, level=100.0))

    def test_zone_not_tested(self):
        df = _frame(lows=[108, 107, 106], closes=[110, 109, 108])
        self.assertFalse(indicators.daily_close_reversal(df, level=100.0, tolerance_pct=0.5))

    def test_test_outside_lookback_does_not_count(self):
        df = _frame(lows=[99, 107, 106, 105], closes=[101, 110, 109, 108])
        self.assertFalse(indicators.daily_close_reversal(df, level=100.0, lookback_bars=3))
        self.assertTrue(indicators.daily_close_reversal(df, level=100.0, lookback_bars=4))

    def test_red_candle_is_rejected_when_bullish_required(self):
        # tested the level and closed above it, but closed below its open (gap-down sell-off day)
        df = _frame(lows=[105, 101, 99.8], closes=[106, 103, 101], opens=[105, 104, 108])
        self.assertTrue(indicators.daily_close_reversal(df, level=100.0))
        self.assertFalse(indicators.daily_close_reversal(df, level=100.0, require_bullish_candle=True))

    def test_green_candle_passes_when_bullish_required(self):
        df = _frame(lows=[105, 101, 99.8], closes=[106, 103, 101], opens=[105, 104, 100.2])
        self.assertTrue(indicators.daily_close_reversal(df, level=100.0, require_bullish_candle=True))

    def test_empty_frame(self):
        self.assertFalse(indicators.daily_close_reversal(_frame([], []), level=100.0))


class SettingsTest(unittest.TestCase):
    def test_current_rule_set_defaults(self):
        s = load_settings()
        self.assertEqual(s.risk.min_net_crv, 3.0)
        self.assertGreater(s.risk.a_setup_net_crv, s.risk.min_net_crv)
        self.assertEqual(s.risk.max_risk_per_trade_eur, 10)
        self.assertTrue(s.analysis.require_daily_close_reversal)
        self.assertTrue(s.analysis.reversal_require_bullish_candle)
        self.assertIsNone(s.analysis.profile_anchor_date)

    def test_unquoted_yaml_date_becomes_string(self):
        raw = Path("config/settings.yaml").read_text(encoding="utf-8")
        raw = raw.replace("profile_anchor_date: null", "profile_anchor_date: 2026-09-18")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.yaml"
            path.write_text(raw, encoding="utf-8")
            self.assertEqual(load_settings(path).analysis.profile_anchor_date, "2026-09-18")


class AnchoredProfileTest(unittest.TestCase):
    def test_anchor_limits_candles(self):
        daily = _synthetic_daily()
        frame, basis = _select_profile_frame(daily, "2026-08-03", "180 Tage")
        self.assertEqual(basis, "ab 2026-08-03")
        self.assertTrue((frame.index >= pd.Timestamp("2026-08-03", tz="UTC")).all())
        self.assertLess(len(frame), len(daily))

    def test_too_few_candles_falls_back(self):
        daily = _synthetic_daily()
        last_day = daily.index[-1].date().isoformat()
        frame, basis = _select_profile_frame(daily, last_day, "180 Tage")
        self.assertEqual(basis, "180 Tage")
        self.assertEqual(len(frame), len(daily))

    def test_no_anchor_keeps_default(self):
        daily = _synthetic_daily()
        frame, basis = _select_profile_frame(daily, None, "180 Tage")
        self.assertEqual(basis, "180 Tage")
        self.assertEqual(len(frame), len(daily))


class RuleGateTest(unittest.TestCase):
    def setUp(self):
        settings = load_settings()
        self.analysis = replace(settings.analysis, proximity_threshold_pct=10.0, require_daily_close_reversal=True)
        self.risk = replace(settings.risk, min_net_crv=0.1, a_setup_net_crv=1.0)

    def _analyze(self, reversal: bool, **kwargs):
        daily = _synthetic_daily()
        with mock.patch("src.signal_engine.fetch_daily", return_value=daily), \
             mock.patch("src.signal_engine.fetch_intraday", return_value=_intraday_turning_up()), \
             mock.patch("src.signal_engine.resample_to_4h", side_effect=lambda df: df), \
             mock.patch("src.signal_engine.get_upcoming_events", return_value=[]), \
             mock.patch("src.signal_engine.get_currency", return_value="EUR"), \
             mock.patch("src.signal_engine.indicators.daily_close_reversal", return_value=reversal):
            return analyze_ticker("TEST", self.analysis, self.risk, display_name="Test", min_confirmations=0, **kwargs)

    def test_alert_requires_reversal(self):
        a = self._analyze(reversal=False)
        self.assertTrue(a.is_hit)
        self.assertFalse(a.is_actionable)
        self.assertFalse(a.rule_checks["daily_close_reversal"])
        self.assertTrue(a.rule_checks["net_crv_ok"])

    def test_alert_with_reversal(self):
        a = self._analyze(reversal=True)
        self.assertTrue(a.is_actionable)
        self.assertTrue(a.daily_close_reversal)
        self.assertIn("daily_candle_bullish", a.rule_checks)

    def test_reversal_not_required(self):
        self.analysis = replace(self.analysis, require_daily_close_reversal=False)
        a = self._analyze(reversal=False)
        self.assertTrue(a.is_actionable)
        self.assertFalse(a.rule_checks["reversal_required"])

    def test_net_crv_still_gates_with_reversal(self):
        self.risk = replace(self.risk, min_net_crv=3.0)
        a = self._analyze(reversal=True)
        self.assertTrue(a.is_hit)
        self.assertFalse(a.rule_checks["net_crv_ok"])
        self.assertFalse(a.is_actionable)

    def test_anchored_profile_is_reported(self):
        self.analysis = replace(self.analysis, profile_anchor_date="2026-08-03")
        a = self._analyze(reversal=True)
        self.assertEqual(a.profile_basis, "ab 2026-08-03")


if __name__ == "__main__":
    unittest.main()
