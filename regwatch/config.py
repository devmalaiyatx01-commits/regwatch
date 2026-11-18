"""Load and check the source list (sources.toml)."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

KINDS = {"feed", "html", "json"}
FETCHERS = {"http", "browser"}


@dataclass(frozen=True)
class Source:
    id: str
    authority: str
    url: str
    kind: str = "feed"
    fetch: str = "http"
    lang: str = "en"
    # html sources only
    row: str = ""
    title: tuple[str, ...] = ()
    link: str = ""
    date: str = ""
    date_format: str = ""
    summary: str = ""
    wait_for: str = ""
    # json sources only: where the list is, and templates filled from each record's fields
    items_key: str = ""
    title_template: str = ""
    summary_template: str = ""
    url_template: str = ""
    date_field: str = ""
    # category to use when no keyword matches (e.g. a page that only lists recalls)
    category_hint: str = ""
    # False for sites that refuse cloud datacenter IPs; skipped when REGWATCH_CLOUD is set
    cloud: bool = True
    # regexes removed before fingerprinting (e.g. "Page last updated ...")
    ignore: tuple[str, ...] = field(default_factory=tuple)


def load_sources(path: str | Path = "sources.toml") -> list[Source]:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    sources = []
    seen = set()
    for raw in data.get("source", []):
        raw = dict(raw)
        for key in ("title", "ignore"):
            if key in raw:
                value = raw[key]
                raw[key] = tuple(value) if isinstance(value, list) else (value,)
        src = Source(**raw)
        problems = check_source(src)
        if src.id in seen:
            problems.append("duplicate id")
        if problems:
            raise ValueError(f"source {src.id!r}: {'; '.join(problems)}")
        seen.add(src.id)
        sources.append(src)
    return sources


def check_source(src: Source) -> list[str]:
    problems = []
    if src.kind not in KINDS:
        problems.append(f"kind must be one of {sorted(KINDS)}")
    if src.fetch not in FETCHERS:
        problems.append(f"fetch must be one of {sorted(FETCHERS)}")
    if not src.url.startswith(("http://", "https://")):
        problems.append("url must be absolute")
    if src.kind == "html" and not (src.row and src.title and src.link):
        problems.append("html sources need row, title and link selectors")
    if src.kind == "json" and not (src.items_key and src.title_template and src.url_template):
        problems.append("json sources need items_key, title_template and url_template")
    return problems
