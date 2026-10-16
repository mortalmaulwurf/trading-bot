import unittest
from datetime import datetime, timezone

from src.status import format_morning_message, is_stale, should_send


def _report(**overrides):
    report = {
        "generated_at_utc": "2026-10-16T22:10:00+00:00",
        "hits_count": 1,
        "alerts_count": 0,
        "errors": {},
        "alerts": [],
        "hits": [
            {
                "name": "Gold", "ticker": "GC=F", "confirmations": 1, "is_actionable": False,
                "position_suggestion": {"net_crv": 1.51},
            }
        ],
        "all_results": [
            {"name": "S&P 500", "ticker": "SPY", "distance_pct": 3.41, "nearest_level_name": "POC"},
            {"name": "DAX", "ticker": "EXS1.DE", "distance_pct": -2.59, "nearest_level_name": "VAL"},
        ],
    }
    report.update(overrides)
    return report


class MorningStatusTest(unittest.TestCase):
    def test_should_send_only_at_8_berlin(self):
        summer_6utc = datetime(2026, 7, 14, 6, 5, tzinfo=timezone.utc)   # 08:05 CEST
        summer_7utc = datetime(2026, 7, 14, 7, 5, tzinfo=timezone.utc)   # 09:05 CEST
        winter_6utc = datetime(2026, 12, 15, 6, 5, tzinfo=timezone.utc)  # 07:05 CET
        winter_7utc = datetime(2026, 12, 15, 7, 5, tzinfo=timezone.utc)  # 08:05 CET
        self.assertTrue(should_send(summer_6utc))
        self.assertFalse(should_send(summer_7utc))
        self.assertFalse(should_send(winter_6utc))
        self.assertTrue(should_send(winter_7utc))
        self.assertTrue(should_send(summer_7utc, force=True))

    def test_staleness_depends_on_weekday(self):
        monday = datetime(2026, 10, 19, 6, 0, tzinfo=timezone.utc)
        tuesday = datetime(2026, 10, 20, 6, 0, tzinfo=timezone.utc)
        self.assertFalse(is_stale(56, monday))   # Friday report on Monday morning is normal
        self.assertTrue(is_stale(56, tuesday))
        self.assertFalse(is_stale(8, tuesday))

    def test_quiet_day_message(self):
        now = datetime(2026, 10, 17, 6, 0, tzinfo=timezone.utc)
        text = format_morning_message(_report(), now)
        self.assertIn("Scan-Status", text)
        self.assertIn("Kein Setup", text)
        self.assertIn("Treffer ohne Setup: Gold - 1/3 Bestätigungen, Netto-CRV 1.51:1", text)
        self.assertIn("S&P 500: 3.4 % über POC", text)
        self.assertIn("DAX: 2.6 % unter VAL", text)
        self.assertNotIn("alt", text)

    def test_stale_and_error_warnings(self):
        now = datetime(2026, 10, 21, 6, 0, tzinfo=timezone.utc)
        text = format_morning_message(_report(errors={"GC=F": "boom"}), now)
        self.assertIn("alt", text)
        self.assertIn("Fehler bei: GC=F", text)

    def test_alerts_listed(self):
        now = datetime(2026, 10, 17, 6, 0, tzinfo=timezone.utc)
        alert = {"name": "DAX", "is_a_setup": True}
        text = format_morning_message(_report(alerts=[alert], alerts_count=1), now)
        self.assertIn("DAX (A-Setup)", text)
        self.assertNotIn("Kein Setup", text)

    def test_markdown_unsafe_characters_are_removed(self):
        now = datetime(2026, 10, 17, 6, 0, tzinfo=timezone.utc)
        text = format_morning_message(_report(errors={"A_B*C": "x"}), now)
        self.assertIn("Fehler bei: ABC", text)


class ErrorMessageTest(unittest.TestCase):
    def test_error_message_lists_tickers_and_strips_markdown(self):
        from src.notifier import format_error_message

        text = format_error_message({"GC=F": "Keine Daten_für [GC]", "SPY": "x" * 400})
        self.assertIn("2 Ticker", text)
        self.assertIn("GC=F: Keine Datenfür GC", text)
        self.assertLess(len(text), 400)


if __name__ == "__main__":
    unittest.main()
