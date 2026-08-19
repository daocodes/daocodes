#!/usr/bin/env python3
"""Write LeetCode easy/medium/hard solved counts into assets/ide.svg.

Reads the public LeetCode GraphQL endpoint — no API key, no scraping, no
third-party service. Run by .github/workflows/neetcode.yml, or by hand:

    python3 scripts/update_neetcode.py --user daocodes --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://leetcode.com/graphql"
QUERY = """
query userProblemsSolved($username: String!) {
  matchedUser(username: $username) {
    submitStatsGlobal { acSubmissionNum { difficulty count } }
  }
}
"""
TRACK = 260.0  # px width of each difficulty track
DIFFICULTIES = ("easy", "medium", "hard")


def fetch(username: str, timeout: int = 30) -> dict[str, int]:
    payload = json.dumps({"query": QUERY, "variables": {"username": username}}).encode()
    request = urllib.request.Request(
        ENDPOINT,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Referer": f"https://leetcode.com/u/{username}/",
            "User-Agent": "Mozilla/5.0 (readme-stats)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        sys.exit(f"error: LeetCode returned HTTP {exc.code}")
    except urllib.error.URLError as exc:
        sys.exit(f"error: could not reach LeetCode ({exc.reason})")

    if body.get("errors"):
        sys.exit(f"error: {body['errors'][0].get('message', 'GraphQL error')}")

    user = (body.get("data") or {}).get("matchedUser")
    if not user:
        sys.exit(f"error: no LeetCode user named {username!r} — check the handle")

    counts = {
        entry["difficulty"].lower(): entry["count"]
        for entry in user["submitStatsGlobal"]["acSubmissionNum"]
    }
    missing = [d for d in DIFFICULTIES if d not in counts]
    if missing:
        sys.exit(f"error: response missing {', '.join(missing)}")
    return counts


def substitute(svg: str, element_id: str, attr: str | None, value: str) -> str:
    if attr:
        pattern = re.compile(rf'(id="{re.escape(element_id)}"[^>]*?{attr}=")[^"]*(")')
    else:
        pattern = re.compile(rf'(<text id="{re.escape(element_id)}"[^>]*>)[^<]*(</text>)')
    svg, n = pattern.subn(rf"\g<1>{value}\g<2>", svg)
    if n != 1:
        sys.exit(f"error: expected 1 match for #{element_id}, got {n} — SVG ids changed?")
    return svg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="your LeetCode username")
    ap.add_argument("--svg", default=pathlib.Path("assets/ide.svg"), type=pathlib.Path)
    ap.add_argument("--dry-run", action="store_true", help="print counts, write nothing")
    args = ap.parse_args()

    counts = fetch(args.user)
    total = sum(counts[d] for d in DIFFICULTIES)
    print(" · ".join(f"{d} {counts[d]}" for d in DIFFICULTIES) + f" · total {total}")

    if args.dry_run:
        return

    svg = args.svg.read_text()
    # Bars are scaled against the largest of the three, so they compare with each
    # other. Scaling against LeetCode's full catalogue would render all three as
    # slivers and say nothing.
    peak = max(counts[d] for d in DIFFICULTIES) or 1
    for difficulty in DIFFICULTIES:
        solved = counts[difficulty]
        svg = substitute(svg, f"nc-bar-{difficulty}", "width", f"{TRACK * solved / peak:.1f}")
        svg = substitute(svg, f"nc-count-{difficulty}", None, str(solved))

    svg = substitute(svg, "nc-total", None, f"{total} problems solved")
    svg = substitute(svg, "nc-badge", None, str(total))
    svg = substitute(
        svg, "nc-stamp", None,
        f"// auto-updated {dt.date.today().isoformat()} from leetcode.com/u/{args.user}",
    )
    args.svg.write_text(svg)
    print(f"wrote {args.svg}")


if __name__ == "__main__":
    main()
