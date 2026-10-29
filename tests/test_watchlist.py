import unittest
from unittest import mock

from src import events
from src.config import load_watchlist


class WatchlistTests(unittest.TestCase):
    def setUp(self):
        self.entries = {e.symbol: e for e in load_watchlist()}

    def test_equity_indices_have_an_index_basis_for_the_certificate_conversion(self):
        for symbol, index_symbol in {
            "SPY": "^GSPC",
            "QQQ": "^NDX",
            "EXS1.DE": "^GDAXI",
            "1321.T": "^N225",
        }.items():
            self.assertIn(symbol, self.entries)
            self.assertEqual(self.entries[symbol].index_symbol, index_symbol)

    def test_symbols_are_unique(self):
        symbols = [e.symbol for e in load_watchlist()]
        self.assertEqual(len(symbols), len(set(symbols)))

    def test_display_names(self):
        self.assertEqual(self.entries["QQQ"].name, "Nasdaq 100")
        self.assertEqual(self.entries["1321.T"].name, "Nikkei 225")


class JapanEventsTests(unittest.TestCase):
    def test_jpy_tickers_get_japan_macro_events_only(self):
        macro = [
            {"date": "2099-01-02", "label": "BoJ-Zinsentscheid", "region": "JP"},
            {"date": "2099-01-02", "label": "EZB", "region": "EU"},
        ]
        with mock.patch.object(events, "get_upcoming_earnings", return_value=None), \
                mock.patch.object(events, "_load_macro_events", return_value=macro), \
                mock.patch("src.events.date") as fake_date:
            from datetime import date as real_date
            fake_date.today.return_value = real_date(2099, 1, 1)
            fake_date.fromisoformat.side_effect = real_date.fromisoformat
            result = events.get_upcoming_events("1321.T", "JPY", 7)
        self.assertEqual(result, ["BoJ-Zinsentscheid am 2099-01-02"])


if __name__ == "__main__":
    unittest.main()
