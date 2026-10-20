"""Tests for the app-style HTML page: rule lights, SVG chart, escaping and graceful degradation."""
import unittest
from dataclasses import replace
from unittest import mock

from src import report as report_module
from src.config import load_settings
from src.formatting import de, price
from src.html_report import render_html
from src.rule_lights import is_paper_candidate, rule_lights
from src.signal_engine import analyze_ticker
from src.svg_chart import render_chart, spread_labels
from tests.test_pipeline import _intraday_turning_up, _synthetic_daily

RULE_SET = {"min_net_crv": 3.0}


def _result(**checks) -> dict:
    base_checks = {
        "level_hit": True,
        "daily_close_reversal": True,
        "daily_candle_bullish": True,
        "reversal_required": True,
        "confirmations_ok": True,
        "net_crv": 3.4,
        "net_crv_ok": True,
    }
    base_checks.update(checks)
    return {
        "ticker": "T", "name": "T", "distance_pct": 1.5, "nearest_level_name": "VAL",
        "is_actionable": False, "rule_checks": base_checks,
    }


def _states(result: dict, rule_set: dict = RULE_SET) -> dict:
    return {light.id: light.state for light in rule_lights(result, rule_set)}


class FormattingTest(unittest.TestCase):
    def test_german_numbers(self):
        self.assertEqual(de(1234.5), "1.234,50")
        self.assertEqual(price(95.8059), "95,8059")
        self.assertEqual(price(100.0), "100,00")


class RuleLightsTest(unittest.TestCase):
    def test_all_passed(self):
        self.assertEqual(_states(_result()), {"level_hit": "pass", "reversal": "pass", "bullish_candle": "pass", "net_crv": "pass"})

    def test_reversal_not_required_is_neutral(self):
        states = _states(_result(daily_close_reversal=False, reversal_required=False, daily_candle_bullish=False))
        self.assertEqual((states["reversal"], states["bullish_candle"]), ("neutral", "neutral"))

    def test_red_candle_fails_with_missing_reversal(self):
        states = _states(_result(daily_close_reversal=False, daily_candle_bullish=False))
        self.assertEqual((states["reversal"], states["bullish_candle"]), ("fail", "fail"))

    def test_missing_candle_info_is_unknown(self):
        self.assertEqual(_states(_result(daily_candle_bullish=None))["bullish_candle"], "unknown")

    def test_net_crv_uses_rule_set_not_bot_flag(self):
        result = _result(net_crv=2.0, net_crv_ok=True)
        self.assertEqual(_states(result)["net_crv"], "fail")

    def test_no_plan_without_hit_is_unknown_with_hit_is_fail(self):
        self.assertEqual(_states(_result(net_crv=None, level_hit=False))["net_crv"], "unknown")
        self.assertEqual(_states(_result(net_crv=None))["net_crv"], "fail")


class PaperCandidateTest(unittest.TestCase):
    def test_flags_only_reversal_or_crv_failures(self):
        self.assertTrue(is_paper_candidate(_result(daily_close_reversal=False), RULE_SET))
        self.assertTrue(is_paper_candidate(_result(net_crv=1.0), RULE_SET))

    def test_ignores_actionable_no_hit_and_other_failures(self):
        self.assertFalse(is_paper_candidate({**_result(), "is_actionable": True}, RULE_SET))
        self.assertFalse(is_paper_candidate(_result(level_hit=False, net_crv=None), RULE_SET))
        self.assertFalse(is_paper_candidate(_result(confirmations_ok=False, net_crv=1.0), RULE_SET))
        self.assertFalse(is_paper_candidate(_result(), RULE_SET))


class SvgChartTest(unittest.TestCase):
    CANDLES = [{"t": "2026-10-01", "o": 10, "h": 12, "l": 9, "c": 11}, {"t": "2026-10-02", "o": 11, "h": 11.5, "l": 8, "c": 9}]

    def test_draws_candles_levels_and_escapes_labels(self):
        svg = render_chart("A<B>", self.CANDLES, [{"label": "S<top>", "price": 8.5, "tone": "stop"}])
        self.assertEqual(svg.count("<rect"), 2)
        self.assertIn("chart-candle--up", svg)
        self.assertIn("chart-candle--down", svg)
        self.assertIn("S&lt;top&gt;", svg)
        self.assertNotIn("<top>", svg)

    def test_empty_and_flat_series(self):
        self.assertEqual(render_chart("x", [], []), "")
        flat = [{"t": "2026-10-01", "o": 10, "h": 10, "l": 10, "c": 10}]
        self.assertIn("<svg", render_chart("x", flat, []))

    def test_spread_labels_keep_gap_and_bottom_edge(self):
        placed = sorted(spread_labels([88, 89, 90], 12, 10, 90))
        self.assertLessEqual(placed[-1], 90)
        self.assertGreaterEqual(placed[1] - placed[0], 12)
        self.assertGreaterEqual(placed[2] - placed[1], 12)


class RenderHtmlTest(unittest.TestCase):
    def setUp(self):
        settings = load_settings()
        analysis = replace(settings.analysis, proximity_threshold_pct=10.0, require_daily_close_reversal=False)
        risk = replace(settings.risk, min_net_crv=0.1, a_setup_net_crv=1.0)
        with mock.patch("src.signal_engine.fetch_daily", return_value=_synthetic_daily()), \
             mock.patch("src.signal_engine.fetch_intraday", return_value=_intraday_turning_up()), \
             mock.patch("src.signal_engine.resample_to_4h", side_effect=lambda df: df), \
             mock.patch("src.signal_engine.get_upcoming_events", return_value=["Quartalszahlen am 2026-10-21"]), \
             mock.patch("src.signal_engine.get_currency", return_value="EUR"):
            self.analysis_result = analyze_ticker("TEST", analysis, risk, display_name="<b>Test</b>", min_confirmations=0)
        self.report = report_module.build_report([self.analysis_result], {"X": "<boom>"}, 10.0, risk, analysis)
        self.charts = report_module.build_charts([self.analysis_result], self.report["generated_at_utc"])

    def test_page_shows_status_lights_chart_plan_and_events(self):
        html = render_html(self.report, self.charts)
        for expected in ("Status: Teilweise", "Regel-Check", "Level-Treffer", "<svg", "Planwerte", "Quartalszahlen", "Setup", "Hebel"):
            self.assertIn(expected, html)

    def test_user_text_is_escaped(self):
        html = render_html(self.report, self.charts)
        self.assertNotIn("<b>Test</b>", html)
        self.assertIn("&lt;b&gt;Test&lt;/b&gt;", html)
        self.assertNotIn("<boom>", html)
        self.assertIn("&lt;boom&gt;", html)

    def test_works_without_charts_and_has_no_external_resources(self):
        html = render_html(self.report)
        self.assertNotIn("<svg", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("src=", html)

    def test_index_levels_are_shown_in_points(self):
        plan = self.report["all_results"][0]["position_suggestion"]
        plan["index_levels"] = {"entry": 24310.5, "stop": 23500.0, "target": None, "required_target": 24900.25}
        html = render_html(self.report, self.charts)
        for expected in ("Index (Punkte)", "24.310,50", "23.500,00", "24.900,25"):
            self.assertIn(expected, html)
        self.assertIn("<dd>–</dd>", html)  # target missing

    def test_no_index_block_without_index_levels(self):
        plan = self.report["all_results"][0]["position_suggestion"]
        plan.pop("index_levels", None)
        self.assertNotIn("Index (Punkte)", render_html(self.report, self.charts))

    def test_old_report_without_rule_set_still_renders(self):
        old = {k: v for k, v in self.report.items() if k not in ("rule_set", "status")}
        self.assertIn("Netto-CRV", render_html(old, self.charts))


if __name__ == "__main__":
    unittest.main()
