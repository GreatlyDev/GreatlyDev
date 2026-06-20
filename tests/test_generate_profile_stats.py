from datetime import date
import unittest

from scripts.generate_profile_stats import (
    aggregate_languages,
    calculate_streaks,
    contribution_total_from_collection,
    normalize_day_entries,
    resolve_profile_stats_token,
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


class ContributionTotalTests(unittest.TestCase):
    def test_adds_restricted_contributions_to_calendar_total(self) -> None:
        collection = {
            "restrictedContributionsCount": 155,
            "contributionCalendar": {"totalContributions": 713},
        }

        self.assertEqual(contribution_total_from_collection(collection), 868)


class ResolveProfileStatsTokenTests(unittest.TestCase):
    def test_prefers_profile_stats_token_over_github_token(self) -> None:
        token = resolve_profile_stats_token(
            {"PROFILE_STATS_TOKEN": "profile-token", "GITHUB_TOKEN": "github-token"}
        )

        self.assertEqual(token, "profile-token")

    def test_falls_back_to_github_token(self) -> None:
        token = resolve_profile_stats_token({"GITHUB_TOKEN": "github-token"})

        self.assertEqual(token, "github-token")


if __name__ == "__main__":
    unittest.main()
