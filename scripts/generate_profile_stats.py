from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from html import escape
import json
import os
from pathlib import Path
from typing import Any
from urllib import parse, request


GRAPHQL_ENDPOINT = "https://api.github.com/graphql"
REST_ENDPOINT = "https://api.github.com"
EXCLUDED_REPOS = {"GreatlyDev"}

CARD_BACKGROUND = "#1f2230"
CARD_PRIMARY = "#70a5fd"
CARD_ACCENT = "#4fd1c5"
CARD_TEXT = "#d6d9e6"
CARD_MUTED = "#9ca3af"

LANGUAGE_COLORS = {
    "Python": "#3776AB",
    "TypeScript": "#3178C6",
    "JavaScript": "#F7DF1E",
    "Java": "#ED8B00",
    "HTML": "#E34F26",
    "CSS": "#1572B6",
    "Dockerfile": "#2496ED",
    "Mako": "#7f52ff",
    "Shell": "#89e051",
}


def github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "GreatlyDev-profile-stats-generator",
    }


def graphql_request(token: str, query: str, variables: dict[str, Any]) -> dict[str, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = request.Request(GRAPHQL_ENDPOINT, data=payload, headers=github_headers(token), method="POST")
    with request.urlopen(req) as response:
        data = json.loads(response.read().decode("utf-8"))
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def rest_request(token: str, url: str) -> Any:
    req = request.Request(url, headers=github_headers(token), method="GET")
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def contribution_years(token: str, username: str) -> list[int]:
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionYears
        }
      }
    }
    """
    data = graphql_request(token, query, {"login": username})
    return data["user"]["contributionsCollection"]["contributionYears"]


def contribution_days_for_year(token: str, username: str, year: int) -> list[dict[str, Any]]:
    start = f"{year}-01-01T00:00:00Z"
    end = f"{year}-12-31T23:59:59Z"
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    data = graphql_request(token, query, {"login": username, "from": start, "to": end})
    weeks = data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days: list[dict[str, Any]] = []
    for week in weeks:
        for day in week["contributionDays"]:
            days.append({"date": day["date"], "count": day["contributionCount"]})
    return days


def normalize_day_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [{"date": str(item["date"]), "count": int(item["count"])} for item in entries]
    normalized.sort(key=lambda item: item["date"])
    return normalized


def calculate_streaks(
    entries: list[dict[str, Any]], today: date | None = None
) -> dict[str, dict[str, Any]]:
    if today is None:
        today = datetime.now(timezone.utc).date()

    longest = {"length": 0, "start": None, "end": None}
    current = {"length": 0, "start": None, "end": None}
    run_length = 0
    run_start: date | None = None
    previous_date: date | None = None

    for item in entries:
        day = date.fromisoformat(item["date"])
        if item["count"] > 0:
            if previous_date and day == previous_date + timedelta(days=1) and run_length > 0:
                run_length += 1
            else:
                run_length = 1
                run_start = day
            if run_length > longest["length"]:
                longest = {
                    "length": run_length,
                    "start": run_start.isoformat() if run_start else None,
                    "end": day.isoformat(),
                }
        else:
            run_length = 0
            run_start = None
        previous_date = day

    positive_days = [date.fromisoformat(item["date"]) for item in entries if item["count"] > 0]
    streak_end = today
    if today not in positive_days:
        streak_end = today - timedelta(days=1)

    positive_set = set(positive_days)
    if streak_end in positive_set:
        cursor = streak_end
        while cursor in positive_set:
            current["length"] += 1
            current["start"] = cursor.isoformat()
            current["end"] = streak_end.isoformat()
            cursor -= timedelta(days=1)

    return {"current": current, "longest": longest}


def fetch_owned_public_repos(token: str, username: str) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    page = 1
    while True:
        params = parse.urlencode({"per_page": 100, "page": page, "type": "owner", "sort": "updated"})
        data = rest_request(token, f"{REST_ENDPOINT}/users/{username}/repos?{params}")
        if not data:
            break
        repos.extend(data)
        page += 1

    filtered = []
    for repo in repos:
        if repo["name"] in EXCLUDED_REPOS:
            continue
        if repo.get("fork") or repo.get("archived") or repo.get("disabled"):
            continue
        if repo.get("size", 0) == 0:
            continue
        filtered.append(repo)
    return filtered


def aggregate_languages(repos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, int] = {}
    for repo in repos:
        for language, count in repo["languages"].items():
            totals[language] = totals.get(language, 0) + int(count)
    ordered = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return [{"name": name, "bytes": count} for name, count in ordered]


def load_languages_for_repos(token: str, repos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for repo in repos:
        languages = rest_request(token, repo["languages_url"])
        enriched.append({"name": repo["name"], "languages": languages})
    return enriched


def format_date_range(summary: dict[str, Any]) -> str:
    if not summary["start"] or not summary["end"]:
        return "No active streak"
    start = format_short_date(date.fromisoformat(summary["start"]))
    end = format_short_date(date.fromisoformat(summary["end"]))
    return f"{start} - {end}"


def format_short_date(value: date) -> str:
    return f"{value.strftime('%b')} {value.day}"


def last_365_total(entries: list[dict[str, Any]], today: date | None = None) -> int:
    if today is None:
        today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    return sum(item["count"] for item in entries if start <= date.fromisoformat(item["date"]) <= today)


def render_stats_svg(total: int, current: dict[str, Any], longest: dict[str, Any]) -> str:
    current_range = escape(format_date_range(current))
    longest_range = escape(format_date_range(longest))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="900" height="250" viewBox="0 0 900 250" role="img" aria-labelledby="title desc">
  <title id="title">GitHub stats</title>
  <desc id="desc">Total contributions {total}, current streak {current['length']}, longest streak {longest['length']}.</desc>
  <rect x="10" y="10" width="880" height="230" rx="18" fill="{CARD_BACKGROUND}"/>
  <line x1="300" y1="35" x2="300" y2="215" stroke="#3b4252" stroke-width="2"/>
  <line x1="600" y1="35" x2="600" y2="215" stroke="#3b4252" stroke-width="2"/>
  <text x="150" y="95" text-anchor="middle" fill="{CARD_PRIMARY}" font-size="38" font-family="Segoe UI, Arial, sans-serif" font-weight="700">{total}</text>
  <text x="150" y="135" text-anchor="middle" fill="{CARD_TEXT}" font-size="24" font-family="Segoe UI, Arial, sans-serif">Total Contributions</text>
  <text x="150" y="175" text-anchor="middle" fill="{CARD_ACCENT}" font-size="20" font-family="Segoe UI, Arial, sans-serif">Last 365 days</text>
  <circle cx="450" cy="90" r="48" fill="none" stroke="{CARD_PRIMARY}" stroke-width="8"/>
  <text x="450" y="102" text-anchor="middle" fill="#c084fc" font-size="38" font-family="Segoe UI, Arial, sans-serif" font-weight="700">{current['length']}</text>
  <text x="450" y="165" text-anchor="middle" fill="{CARD_TEXT}" font-size="24" font-family="Segoe UI, Arial, sans-serif">Current Streak</text>
  <text x="450" y="198" text-anchor="middle" fill="{CARD_ACCENT}" font-size="20" font-family="Segoe UI, Arial, sans-serif">{current_range}</text>
  <text x="750" y="95" text-anchor="middle" fill="{CARD_PRIMARY}" font-size="38" font-family="Segoe UI, Arial, sans-serif" font-weight="700">{longest['length']}</text>
  <text x="750" y="135" text-anchor="middle" fill="{CARD_TEXT}" font-size="24" font-family="Segoe UI, Arial, sans-serif">Longest Streak</text>
  <text x="750" y="175" text-anchor="middle" fill="{CARD_ACCENT}" font-size="20" font-family="Segoe UI, Arial, sans-serif">{longest_range}</text>
</svg>"""


def render_languages_svg(languages: list[dict[str, Any]]) -> str:
    top = languages[:6]
    total = sum(item["bytes"] for item in top) or 1
    bar_x = 80
    bar_y = 70
    bar_width = 520
    bar_height = 16
    legend_y = 120
    segments = []
    legends = []
    current_x = bar_x

    for index, item in enumerate(top):
        width = round((item["bytes"] / total) * bar_width, 2)
        color = LANGUAGE_COLORS.get(item["name"], "#94a3b8")
        percent = (item["bytes"] / total) * 100
        segments.append(
            f'<rect x="{current_x}" y="{bar_y}" width="{width}" height="{bar_height}" rx="4" fill="{color}"/>'
        )
        legends.append(
            f'<circle cx="{95 + (index % 2) * 255}" cy="{legend_y + (index // 2) * 38}" r="6" fill="{color}"/>'
            f'<text x="{110 + (index % 2) * 255}" y="{legend_y + 6 + (index // 2) * 38}" fill="{CARD_TEXT}" font-size="18" font-family="Segoe UI, Arial, sans-serif">{escape(item["name"])} {percent:.2f}%</text>'
        )
        current_x += width

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="700" height="260" viewBox="0 0 700 260" role="img" aria-labelledby="title desc">
  <title id="title">Most used languages</title>
  <desc id="desc">Top languages aggregated from owned public repositories.</desc>
  <rect x="10" y="10" width="680" height="240" rx="18" fill="{CARD_BACKGROUND}"/>
  <text x="350" y="46" text-anchor="middle" fill="{CARD_PRIMARY}" font-size="34" font-family="Segoe UI, Arial, sans-serif" font-weight="700">Most Used Languages</text>
  {''.join(segments)}
  {''.join(legends)}
</svg>"""


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> None:
    token = os.environ["PROFILE_STATS_TOKEN"]
    username = os.environ.get("PROFILE_STATS_USERNAME", "GreatlyDev")
    output_dir = Path(os.environ.get("PROFILE_STATS_OUTPUT_DIR", "dist/generated"))

    day_entries: list[dict[str, Any]] = []
    for year in contribution_years(token, username):
        day_entries.extend(contribution_days_for_year(token, username, year))

    normalized_days = normalize_day_entries(day_entries)
    streaks = calculate_streaks(normalized_days)
    total = last_365_total(normalized_days)

    repos = fetch_owned_public_repos(token, username)
    language_repos = load_languages_for_repos(token, repos)
    languages = aggregate_languages(language_repos)

    write_file(output_dir / "github-stats.svg", render_stats_svg(total, streaks["current"], streaks["longest"]))
    write_file(output_dir / "top-languages.svg", render_languages_svg(languages))


if __name__ == "__main__":
    main()
