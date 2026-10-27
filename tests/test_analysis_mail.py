"""Tests for the HTML email renderer: sections, escaping, email-safe markup and graceful degradation."""
import json
import unittest
from pathlib import Path

from src import analysis_mail as mail

SAMPLE = json.loads((Path(__file__).parent / "fixtures" / "analysis_sample.json").read_text(encoding="utf-8"))


class RenderEmailTest(unittest.TestCase):
    def setUp(self):
        self.html = mail.render_email(SAMPLE)

    def test_contains_all_sections(self):
        for expected in ("Wochenausblick", "Fazit", "Auf einen Blick", "Wochenperformance", "Preisleiter",
                         "Marktdaten", "Termine und Lernhilfe", "Warum wichtig", "Worauf achten",
                         "Mögliche Reaktion", "Alarme für heute", "Regel-Check", "Lücken und Unsicherheiten",
                         "keine Anlageberatung"):
            self.assertIn(expected, self.html)

    def test_is_email_safe(self):
        lowered = self.html.lower()
        for forbidden in ("<script", "<svg", "<img", "<link", "http://", "https://", "display:flex", "display:grid"):
            self.assertNotIn(forbidden, lowered)
        self.assertLess(len(self.html), 100_000)  # Gmail clips larger messages

    def test_german_date_and_numbers(self):
        self.assertIn("Sonntag, 25. Oktober 2026", self.html)
        self.assertIn("25.182", self.html)
        self.assertIn("−0,75 %", self.html)

    def test_user_text_is_escaped(self):
        data = {"date": "2026-10-26", "verdict": {"label": "<b>Test</b>", "text": "a & b <script>x</script>"},
                "instruments": [{"name": "<i>X</i>", "close": 1.5}], "gaps": ["<img src=x>"]}
        html = mail.render_email(data)
        self.assertNotIn("<b>Test</b>", html)
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;b&gt;Test&lt;/b&gt;", html)

    def test_minimal_and_empty_input_do_not_crash(self):
        self.assertIn("Marktanalyse", mail.render_email({}))
        self.assertIn("Tagesbriefing", mail.render_email({"date": "2026-10-26", "mode": "daily"}))
        self.assertIn("kaputt", mail.render_email({"date": "kaputt"}))

    def test_invalid_numbers_are_skipped(self):
        data = {"instruments": [{"name": "A", "close": "n/a", "day_pct": None, "closes": [1, "x", float("nan"), None],
                                 "levels": {"val": "?", "poc": None}, "rsi": "abc"}]}
        html = mail.render_email(data)
        self.assertIn("–", html)
        self.assertNotIn("nan", html.lower().replace("financial", ""))


class ChartsTest(unittest.TestCase):
    def test_sparkline_needs_two_values_and_caps_bars(self):
        self.assertEqual(mail._sparkline([1]), "")
        spark = mail._sparkline(list(range(100)))
        self.assertEqual(spark.count("<td valign"), mail.MAX_BARS)

    def test_sparkline_flat_series(self):
        self.assertIn("<div", mail._sparkline([5, 5, 5]))

    def test_sparkline_colors_follow_direction(self):
        spark = mail._sparkline([1, 2, 1])
        self.assertLess(spark.index("#16a34a"), spark.index("#dc2626"))

    def test_ladder_orders_prices_descending(self):
        ladder = mail._ladder({"val": 90, "poc": 100, "vah": 110}, 95)
        order = [ladder.index(label) for label in ("VAH", "POC", "Schluss", "VAL")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(mail._ladder({"val": 1}, None), "")

    def test_perf_chart_bars_follow_sign(self):
        chart = mail._perf_chart([{"label": "A", "pct": -2.0}, {"label": "B", "pct": 1.0}, {"label": "C", "pct": None}])
        self.assertIn('align="right"', chart)
        self.assertIn("#16a34a", chart)
        self.assertNotIn(">C<", chart)
        self.assertEqual(mail._perf_chart([]), "")

    def test_perf_chart_is_not_distorted_by_vix(self):
        data = {"instruments": [{"name": "DAX", "week_pct": -1.7}], "market": [{"label": "VIX", "week_pct": 21.4}]}
        self.assertNotIn("VIX", mail._perf_chart([{"label": "DAX", "pct": -1.7}]))
        self.assertNotIn(">VIX<", mail.render_email(data).split("Wochenperformance")[1].split("Marktdaten")[0])

    def test_rsi_gauge_zones(self):
        self.assertIn("überverkauft", mail._rsi_gauge(25))
        self.assertIn("überkauft", mail._rsi_gauge(75))
        self.assertIn("neutral", mail._rsi_gauge(50))
        self.assertEqual(mail._rsi_gauge(None), "")


class SubjectAndTextTest(unittest.TestCase):
    def test_subject_has_date_verdict_and_first_move(self):
        subject = mail.render_subject(SAMPLE)
        self.assertEqual(subject, "Wochenausblick 25. Oktober 2026 · Kein Einstieg zum Wochenstart · DAX −0,8 %")

    def test_subject_without_data(self):
        self.assertEqual(mail.render_subject({"date": "2026-10-26"}), "Marktanalyse 26. Oktober 2026")

    def test_plain_text_alternative(self):
        text = mail.render_text(SAMPLE)
        self.assertIn("Fazit: Kein Einstieg zum Wochenstart", text)
        self.assertIn("DAX", text)
        self.assertNotIn("<", text)


if __name__ == "__main__":
    unittest.main()
