"""Onboarding checks for a new or changed source. Run before adding it to the schedule."""
from __future__ import annotations

from collections import Counter

from .fetch import allowed_by_robots, fetch
from .lang import detect_language
from .parse import parse

MIN_ITEMS = 3


def validate_source(source) -> list[tuple[str, bool, str]]:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> bool:
        checks.append((name, ok, detail))
        return ok

    if not check("robots.txt allows fetching", allowed_by_robots(source.url)):
        return checks
    try:
        result = fetch(source)
    except Exception as exc:
        check("fetch succeeds", False, str(exc)[:200])
        return checks
    if not check("HTTP 200", result.status == 200, f"got {result.status} in {result.elapsed_ms} ms via {result.via}"):
        return checks
    try:
        items = parse(source, result)
    except Exception as exc:
        check("parses", False, f"{type(exc).__name__}: {exc}"[:200])
        return checks
    check(f"at least {MIN_ITEMS} items", len(items) >= MIN_ITEMS, f"{len(items)} items")
    if not items:
        return checks
    check("all links absolute http(s)", all(i.url.startswith(("http://", "https://")) for i in items))
    check("no duplicate links", len({i.url for i in items}) == len(items))
    dated = sum(1 for i in items if i.published)
    check("80% of items have a parsable date", dated >= 0.8 * len(items), f"{dated}/{len(items)} dated")
    langs = Counter(detect_language(f"{i.title} {i.summary}")[0] for i in items)
    share = langs.get(source.lang, 0) / len(items)
    check(f"titles look like '{source.lang}'", share >= 0.6,
          ", ".join(f"{k}:{v}" for k, v in langs.most_common(4)))
    check("titles are not empty or boilerplate", len({i.title for i in items}) >= 0.8 * len(items),
          f"{len({i.title for i in items})} distinct titles")
    return checks
