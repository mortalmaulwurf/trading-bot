"""Unit tests for the Strict Coach Mode sizing (variable leverage, costs, net CRV)."""
import unittest
from dataclasses import replace

from src.config import RiskSettings
from src.risk import suggest_position

BASE = RiskSettings(
    total_capital_eur=300,
    max_position_eur=300,
    max_risk_per_trade_eur=10,
    ko_buffer=0.5,
    max_leverage=20,
    fee_per_order_eur=1.0,
    min_free_order_volume_eur=500,
    spread_pct=0.5,
    risk_includes_costs=True,
    min_net_crv=3.0,
    a_setup_net_crv=3.0,
    atr_period=14,
    stop_atr_multiple=1.0,
)


class SuggestPositionTest(unittest.TestCase):
    def test_matches_trade_calculator_example(self):
        # DAX long 25150 / stop 24770 / target 26200, same numbers as the Trade-Rechner artifact.
        p = suggest_position(25150, 24770, 26200, "EUR", BASE)
        self.assertIsNotNone(p)
        self.assertEqual(p.leverage, 20)
        self.assertAlmostEqual(p.capital_eur, 26.04, places=1)
        self.assertAlmostEqual(p.costs_eur, 2.13, places=1)
        self.assertAlmostEqual(p.total_loss_eur, 10.0, places=2)
        self.assertAlmostEqual(p.gross_crv, 2.76, places=2)
        self.assertAlmostEqual(p.net_crv, 1.96, places=2)
        self.assertAlmostEqual(p.required_target_price, 26701.4, places=0)

    def test_max_leverage_cap_is_respected(self):
        p = suggest_position(25150, 24770, 26200, "EUR", replace(BASE, max_leverage=10))
        self.assertEqual(p.leverage, 10)
        self.assertEqual(p.max_leverage_by_buffer, 44)

    def test_ko_buffer_limits_leverage_for_wide_stops(self):
        # 5% stop -> KO must be >= 7.5% away -> at most 13x
        p = suggest_position(100.0, 95.0, 110.0, "EUR", replace(BASE, max_leverage=50))
        self.assertEqual(p.max_leverage_by_buffer, 13)
        self.assertEqual(p.leverage, 13)
        self.assertGreaterEqual(1 / p.leverage * 100, p.min_ko_distance_pct - 1e-9)

    def test_loss_at_stop_never_exceeds_budget_when_costs_included(self):
        for stop in (24000, 24500, 24900, 25100):
            p = suggest_position(25150, stop, 27000, "EUR", BASE)
            self.assertLessEqual(p.total_loss_eur, BASE.max_risk_per_trade_eur + 1e-6)

    def test_position_is_capped(self):
        p = suggest_position(100.0, 99.9, 101.0, "EUR", replace(BASE, max_leverage=2))
        self.assertTrue(p.capped)
        self.assertAlmostEqual(p.capital_eur, 300.0)
        self.assertLessEqual(p.total_loss_eur, BASE.max_risk_per_trade_eur)

    def test_required_target_reaches_min_net_crv(self):
        p = suggest_position(25150, 24770, 26200, "EUR", BASE)
        at_required = suggest_position(25150, 24770, p.required_target_price, "EUR", BASE)
        self.assertAlmostEqual(at_required.net_crv, BASE.min_net_crv, places=3)

    def test_no_fee_at_or_above_free_volume(self):
        p = suggest_position(100.0, 99.0, 103.0, "EUR", replace(BASE, max_leverage=2, max_position_eur=1000, min_free_order_volume_eur=100))
        self.assertGreaterEqual(p.capital_eur, 100)
        self.assertAlmostEqual(p.costs_eur, p.capital_eur * 0.005, places=6)

    def test_invalid_stop_returns_none(self):
        self.assertIsNone(suggest_position(100.0, 100.0, 110.0, "EUR", BASE))
        self.assertIsNone(suggest_position(100.0, 101.0, 110.0, "EUR", BASE))

    def test_no_target_means_no_crv(self):
        p = suggest_position(100.0, 98.0, None, "EUR", BASE)
        self.assertIsNone(p.net_crv)
        self.assertIsNone(p.gross_crv)


if __name__ == "__main__":
    unittest.main()
