"""One monitoring run over all sources."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

import requests

from .classify import RuleClassifier
from .detect import Change, State, detect_changes
from .fetch import FetchError, allowed_by_robots, fetch
from .lang import detect_language
from .parse import parse

log = logging.getLogger("regwatch")
FAILURES_BEFORE_ALERT = 2


@dataclass
class SourceRun:
    source_id: str
    authority: str
    status: str = "ok"           # ok | error | empty | blocked
    items: int = 0
    new: int = 0
    revised: int = 0
    baseline: int = 0
    elapsed_ms: int = 0
    via: str = ""
    error: str = ""
    consecutive_failures: int = 0

    @property
    def degraded(self) -> bool:
        return self.consecutive_failures >= FAILURES_BEFORE_ALERT


@dataclass
class RunReport:
    started: str
    sources: list[SourceRun] = field(default_factory=list)
    changes: list[dict] = field(default_factory=list)
    llm_usage: dict | None = None

    @property
    def degraded(self) -> list[SourceRun]:
        return [s for s in self.sources if s.degraded]


def item_language(item, default: str) -> str:
    lang, confidence = detect_language(f"{item.title} {item.summary}")
    return lang if lang != "und" and confidence >= 0.3 else default


def run(sources, state: State, classifier=None, now: str | None = None) -> RunReport:
    now = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rules = RuleClassifier()
    classifier = classifier or rules
    report = RunReport(started=now)
    session = requests.Session()

    in_cloud = bool(os.environ.get("REGWATCH_CLOUD"))
    for source in sources:
        sr = SourceRun(source.id, source.authority, via=source.fetch)
        if in_cloud and not source.cloud:
            # Some sites refuse datacenter IPs (bot protection, geo-blocking). They run from a
            # local machine instead; skipping here is not a failure and does not touch health.
            sr.status, sr.error = "skipped", "refuses cloud IPs; runs from a local machine"
            report.sources.append(sr)
            continue
        health = state.health.setdefault(source.id, {"consecutive_failures": 0, "last_ok": None})
        try:
            if not allowed_by_robots(source.url, session):
                raise FetchError("disallowed by robots.txt")
            result = fetch(source, session)
            sr.elapsed_ms = result.elapsed_ms
            if result.status != 200:
                raise FetchError(f"HTTP {result.status}")
            items = parse(source, result)
            sr.items = len(items)
            if not items:
                raise FetchError("parsed 0 items (selector or feed format changed?)")
        except Exception as exc:  # one broken source must not stop the run
            sr.status = "blocked" if "robots" in str(exc) else ("empty" if "0 items" in str(exc) else "error")
            sr.error = str(exc)[:300]
            health["consecutive_failures"] += 1
            sr.consecutive_failures = health["consecutive_failures"]
            health.update(last_run=now, status=sr.status, error=sr.error)
            log.warning("%s failed (%s in a row): %s", source.id, sr.consecutive_failures, sr.error)
            report.sources.append(sr)
            continue

        changes, sr.baseline = detect_changes(items, state, source, now)
        changed_urls = {c.item.url for c in changes}
        for item in items:
            record = state.items[item.url]
            if item.url in changed_urls or "category" not in record:
                lang = item_language(item, source.lang)
                use = classifier if item.url in changed_urls else rules
                result = use.classify(item.title, item.summary, hint=source.category_hint,
                                      authority=source.authority, lang=lang)
                record.update(lang=lang, **{k: v for k, v in result.to_dict().items()})
        for change in changes:
            record = state.items[change.item.url]
            sr.new += change.kind == "new"
            sr.revised += change.kind == "revised"
            report.changes.append({**record, "url": change.item.url, "authority": source.authority,
                                   "change": change.kind, "diff": change.diff})
        health.update(consecutive_failures=0, last_ok=now, last_run=now, status="ok", error="",
                      items=sr.items)
        report.sources.append(sr)
        log.info("%s: %d items, %d new, %d revised", source.id, sr.items, sr.new, sr.revised)

    report.changes.sort(key=lambda c: (-c["priority"], c["source"]))
    report.llm_usage = getattr(classifier, "usage", None)
    return report
