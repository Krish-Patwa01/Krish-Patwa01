"""
Pulls live contribution data from GitHub's GraphQL API and draws it as four
SVGs in the same visual language as the portrait:

    stats.svg   hero total + weekly sparkline (columns, not a line through
                sparse/discrete daily counts)
    streak.svg  current and longest streak, with date ranges
    langs.svg   top languages, by bytes and by repo count
    year.svg    one character per day, using the portrait's own ramp

Deliberately stdlib-only (urllib, json, datetime, base64) — this is the
script the nightly GitHub Action runs, and a third-party dependency that
breaks in CI is exactly the failure mode this whole project exists to avoid.
The font is NOT subset here: fonts/subset-data-*.woff2 were built once,
locally, by scripts/generate_headings_font.py and just get read + inlined.

Two determinism traps this avoids (see the write-up):
  1. Pin the window to whole UTC days, or two runs minutes apart bucket
     days into different weeks and the sparkline shifts every night.
  2. Filter repositories to `privacy: PUBLIC` — the workflow's token can't
     see private repos, so language percentages must be computed the same
     way a public viewer would see them, not however the personal token
     that ran the script locally would.

Env vars:
    GITHUB_TOKEN   a token with read access to the GraphQL API (the
                   workflow's own built-in GITHUB_TOKEN is enough)
    GH_LOGIN       the GitHub login to report on
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import os
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

REPO_ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = REPO_ROOT / "fonts"
OUT_DIR = REPO_ROOT  # stats.svg etc live at repo root, per the workflow

GRAPHQL_URL = "https://api.github.com/graphql"

RAMP = " .`:-=+*cs#%@"

INK_LIGHT = "#1b1f24"
INK_DARK = "#c9d1d9"
MUTED_LIGHT = "#57606a"
MUTED_DARK = "#8b949e"
FONT_FAMILY = "ProfileMono"

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false) {
      nodes {
        name
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges {
            size
            node { name color }
          }
        }
      }
    }
  }
}
"""


def graphql(token: str, query: str, variables: dict) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "profile-stats-script",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise RuntimeError(f"GraphQL error: {payload['errors']}")
    return payload["data"]


def fetch(login: str, token: str) -> dict:
    # whole-UTC-day window — the first determinism trap. Two runs minutes
    # apart must bucket the same days into the same weeks.
    today = dt.datetime.now(dt.timezone.utc).date()
    to = dt.datetime.combine(today, dt.time(23, 59, 59), tzinfo=dt.timezone.utc)
    frm = dt.datetime.combine(
        today - dt.timedelta(days=364), dt.time(0, 0, 0), tzinfo=dt.timezone.utc
    )
    data = graphql(
        token, QUERY,
        {"login": login, "from": frm.isoformat(), "to": to.isoformat()},
    )
    return data["user"]


# ---------------------------------------------------------------- font ----

def _font_face_css(family: str, woff2_path: Path, weight: int) -> str:
    b64 = base64.b64encode(woff2_path.read_bytes()).decode("ascii")
    return (
        f"@font-face{{font-family:'{family}';font-weight:{weight};"
        f"src:url(data:font/woff2;charset=utf-8;base64,{b64}) format('woff2');}}"
    )


def _data_font_css() -> str:
    reg = FONTS_DIR / "subset-data-regular.woff2"
    bold = FONTS_DIR / "subset-data-bold.woff2"
    css = _font_face_css(FONT_FAMILY, reg, 400)
    if bold.exists():
        css += _font_face_css(FONT_FAMILY, bold, 700)
    return css


def _ramp_font_css() -> str:
    ramp = FONTS_DIR / "subset-ramp.woff2"
    return _font_face_css("ProfileRamp", ramp, 400)


def _svg_header(width: float, height: float, display_width: int, label: str, extra_style: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" '
        f'viewBox="0 0 {width:.2f} {height:.2f}" width="{display_width}" '
        f'role="img" aria-label="{xml_escape(label)}">'
        f"<style>{_data_font_css()}"
        f"text{{font-family:'{FONT_FAMILY}',ui-monospace,monospace;white-space:pre;}}"
        f"{extra_style}</style>"
    )


# --------------------------------------------------------------- stats ----

def build_stats_svg(calendar: dict, ink: str, muted: str) -> str:
    weeks = calendar["weeks"]
    total = calendar["totalContributions"]
    weekly_totals = [
        sum(d["contributionCount"] for d in w["contributionDays"]) for w in weeks
    ]
    # last 20 weeks as the sparkline — recent enough to be legible as columns
    recent = weekly_totals[-20:]
    max_v = max(recent) if recent and max(recent) > 0 else 1

    W, H = 460, 140
    svg = _svg_header(
        W, H, 460, f"{total} contributions in the last year",
        f".muted{{fill:{muted};}}.bar{{fill:{ink};}}"
        f"text{{fill:{ink};}}",
    )
    svg += f'<text x="0" y="28" font-size="26" font-weight="700">{total:,}</text>'
    svg += f'<text class="muted" x="0" y="46" font-size="12">contributions in the last year</text>'

    chart_top, chart_h, chart_bottom = 64, 56, 120
    bar_w = W / len(recent)
    for i, v in enumerate(recent):
        bar_h = (v / max_v) * chart_h if v else 0
        x = i * bar_w
        y = chart_bottom - bar_h
        # a zero week is honestly empty space, not a hairline bar
        if bar_h > 0:
            svg += f'<rect class="bar" x="{x + bar_w * 0.15:.2f}" y="{y:.2f}" width="{bar_w * 0.7:.2f}" height="{bar_h:.2f}"/>'
    svg += f'<line class="muted" x1="0" y1="{chart_bottom}" x2="{W}" y2="{chart_bottom}" stroke="{muted}" stroke-width="1"/>'
    svg += f'<text class="muted" x="0" y="{chart_bottom + 16}" font-size="10">last 20 weeks</text>'
    svg += "</svg>"
    return svg


# -------------------------------------------------------------- streak ----

def compute_streaks(calendar: dict) -> dict:
    days = [
        (d["date"], d["contributionCount"])
        for w in calendar["weeks"]
        for d in w["contributionDays"]
    ]
    days.sort(key=lambda t: t[0])

    longest = cur = 0
    longest_range = cur_range = None
    run_start = None
    for date_s, count in days:
        if count > 0:
            if run_start is None:
                run_start = date_s
            cur += 1
            if cur > longest:
                longest = cur
                longest_range = (run_start, date_s)
        else:
            run_start = None
            cur = 0

    # current streak: walk backwards from the last day with data
    current = 0
    current_range = None
    run_end = None
    for date_s, count in reversed(days):
        if count > 0:
            if run_end is None:
                run_end = date_s
            current += 1
            current_range = (date_s, run_end)
        else:
            break

    return {
        "current": current,
        "current_range": current_range,
        "longest": longest,
        "longest_range": longest_range,
    }


def build_streak_svg(streaks: dict, ink: str, muted: str) -> str:
    W, H = 460, 100
    svg = _svg_header(W, H, 460, "contribution streak", f"text{{fill:{ink};}}.muted{{fill:{muted};}}")

    def col(x, label, value, date_range):
        out = f'<text x="{x}" y="34" font-size="28" font-weight="700">{value}</text>'
        out += f'<text class="muted" x="{x}" y="52" font-size="11">{xml_escape(label)}</text>'
        if date_range:
            out += f'<text class="muted" x="{x}" y="68" font-size="10">{date_range[0]} → {date_range[1]}</text>'
        return out

    svg += col(0, "current streak", streaks["current"], streaks["current_range"])
    svg += col(240, "longest streak", streaks["longest"], streaks["longest_range"])
    svg += f'<line x1="220" y1="10" x2="220" y2="80" stroke="{muted}" stroke-width="1"/>'
    svg += "</svg>"
    return svg


# --------------------------------------------------------------- langs ----

def aggregate_languages(repos: list[dict]) -> list[dict]:
    totals: dict[str, dict] = {}
    for repo in repos:
        seen_in_repo = set()
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            color = edge["node"]["color"] or "#999999"
            size = edge["size"]
            entry = totals.setdefault(name, {"bytes": 0, "repos": 0, "color": color})
            entry["bytes"] += size
            if name not in seen_in_repo:
                entry["repos"] += 1
                seen_in_repo.add(name)
    ranked = sorted(totals.items(), key=lambda kv: kv[1]["bytes"], reverse=True)
    return [{"name": n, **v} for n, v in ranked[:6]]


def build_langs_svg(langs: list[dict], ink: str, muted: str) -> str:
    W, H = 460, 30 + 22 * max(len(langs), 1)
    svg = _svg_header(W, H, 460, "top languages", f"text{{fill:{ink};}}.muted{{fill:{muted};}}")
    total_bytes = sum(l["bytes"] for l in langs) or 1
    bar_x, bar_w_max = 150, 220
    y = 14
    for l in langs:
        pct = l["bytes"] / total_bytes
        bar_w = bar_w_max * pct
        svg += f'<text x="0" y="{y+4}" font-size="11">{xml_escape(l["name"])}</text>'
        svg += f'<rect x="{bar_x}" y="{y-6}" width="{bar_w_max}" height="8" fill="{muted}" opacity="0.25"/>'
        svg += f'<rect x="{bar_x}" y="{y-6}" width="{bar_w:.2f}" height="8" fill="{ink}"/>'
        svg += f'<text class="muted" x="{bar_x + bar_w_max + 10}" y="{y+4}" font-size="10">{pct*100:.0f}% · {l["repos"]} repo{"s" if l["repos"] != 1 else ""}</text>'
        y += 22
    svg += "</svg>"
    return svg


# ---------------------------------------------------------------- year ----

def build_year_svg(calendar: dict, ink: str, muted: str) -> str:
    days = [d["contributionCount"] for w in calendar["weeks"] for d in w["contributionDays"]]
    nonzero = sorted(c for c in days if c > 0)

    ramp_len = len(RAMP)

    def bucket(count: int) -> int:
        if count <= 0 or not nonzero:
            return 0
        # quantile bucketing into the remaining ramp levels, so one wildly
        # busy day doesn't flatten every other day into the lightest mark
        rank = sum(1 for v in nonzero if v <= count) / len(nonzero)
        idx = 1 + round(rank * (ramp_len - 2))
        return min(idx, ramp_len - 1)

    CHAR_W, CHAR_H = 7, 11
    weeks = calendar["weeks"]
    W = len(weeks) * CHAR_W
    H = 7 * CHAR_H + 20

    ramp_css = _ramp_font_css()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" '
        f'viewBox="0 0 {W:.2f} {H:.2f}" width="700" role="img" aria-label="contributions this year">'
        f"<style>{ramp_css}"
        f"text{{font-family:'ProfileRamp',ui-monospace,monospace;font-size:11px;fill:{ink};}}</style>"
    )
    for wi, week in enumerate(weeks):
        for di, day in enumerate(week["contributionDays"]):
            ch = RAMP[bucket(day["contributionCount"])]
            if ch == " ":
                continue
            x = wi * CHAR_W
            y = 10 + di * CHAR_H
            svg += f'<text x="{x}" y="{y}">{xml_escape(ch)}</text>'
    svg += "</svg>"
    return svg


# ---------------------------------------------------------------- main ----

def main():
    token = os.environ["GITHUB_TOKEN"]
    login = os.environ["GH_LOGIN"]

    user = fetch(login, token)
    calendar = user["contributionsCollection"]["contributionCalendar"]
    repos = user["repositories"]["nodes"]
    streaks = compute_streaks(calendar)
    langs = aggregate_languages(repos)

    pairs = [
        ("stats", build_stats_svg(calendar, INK_LIGHT, MUTED_LIGHT),
                  build_stats_svg(calendar, INK_DARK, MUTED_DARK)),
        ("streak", build_streak_svg(streaks, INK_LIGHT, MUTED_LIGHT),
                   build_streak_svg(streaks, INK_DARK, MUTED_DARK)),
        ("langs", build_langs_svg(langs, INK_LIGHT, MUTED_LIGHT),
                  build_langs_svg(langs, INK_DARK, MUTED_DARK)),
        ("year", build_year_svg(calendar, INK_LIGHT, MUTED_LIGHT),
                 build_year_svg(calendar, INK_DARK, MUTED_DARK)),
    ]

    svg_dir = OUT_DIR / "svg"
    svg_dir.mkdir(exist_ok=True)
    for name, light, dark in pairs:
        (svg_dir / f"{name}-light.svg").write_text(light, encoding="utf-8")
        (svg_dir / f"{name}-dark.svg").write_text(dark, encoding="utf-8")
        print(f"wrote {name}-light.svg / {name}-dark.svg")


if __name__ == "__main__":
    main()
