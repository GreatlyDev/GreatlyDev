from datetime import date
import unittest

from scripts.generate_profile_stats import (
    aggregate_languages,
    calculate_streaks,
    normalize_day_entries,
)


class CalculateStreaksTests(unittest.TestCase):
    def test_calculates_current_and_longest_streaks(self) -> None:
        days = normalize_day_entries(
            [
                {"date": "2026-04-01", "count": 1},
                {"date": "2026-04-02", "count": 2},
                {"date": "2026-04-03", "count": 0},
                {"date": "2026-04-04", "count": 1},
                {"date": "2026-04-05", "count": 1},
                {"date": "2026-04-06", "count": 1},
            ]
        )

        summary = calculate_streaks(days, today=date(2026, 4, 6))

        self.assertEqual(summary["current"]["length"], 3)
        self.assertEqual(summary["current"]["start"], "2026-04-04")
        self.assertEqual(summary["current"]["end"], "2026-04-06")
        self.assertEqual(summary["longest"]["length"], 3)
        self.assertEqual(summary["longest"]["start"], "2026-04-04")
        self.assertEqual(summary["longest"]["end"], "2026-04-06")

    def test_zero_when_today_has_no_contribution_and_no_prior_run(self) -> None:
        days = normalize_day_entries(
            [
                {"date": "2026-04-01", "count": 0},
                {"date": "2026-04-02", "count": 0},
            ]
        )

        summary = calculate_streaks(days, today=date(2026, 4, 2))

        self.assertEqual(summary["current"]["length"], 0)
        self.assertIsNone(summary["current"]["start"])
        self.assertIsNone(summary["current"]["end"])


class AggregateLanguagesTests(unittest.TestCase):
    def test_aggregates_and_sorts_languages(self) -> None:
        repos = [
            {"name": "alpha", "languages": {"Python": 300, "HTML": 100}},
            {"name": "beta", "languages": {"Python": 100, "TypeScript": 200}},
            {"name": "gamma", "languages": {"JavaScript": 50}},
        ]

        result = aggregate_languages(repos)

        self.assertEqual(result[0]["name"], "Python")
        self.assertEqual(result[0]["bytes"], 400)
        self.assertEqual(result[1]["name"], "TypeScript")
        self.assertEqual(result[2]["name"], "HTML")
        self.assertEqual(result[3]["name"], "JavaScript")


if __name__ == "__main__":
    unittest.main()
