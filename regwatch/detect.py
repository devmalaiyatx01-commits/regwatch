"""Change detection: decide which items are new, revised or unchanged.

Each item is fingerprinted with SHA-256 over its normalised title, date and summary.
Normalisation (NFKC, whitespace collapse, per-source ignore patterns) stops markup or
"page last updated" noise from showing up as a revision. State is a plain JSON file so
every run's changes are readable in git history.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


def normalise_for_hash(text: str, ignore: tuple[str, ...] = ()) -> str:
    text = unicodedata.normalize("NFKC", text)
    for pattern in ignore:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def fingerprint(item, ignore: tuple[str, ...] = ()) -> str:
    raw = "\n".join([item.title, item.published or "", item.summary])
    return hashlib.sha256(normalise_for_hash(raw, ignore).encode("utf-8")).hexdigest()


def word_diff(old: str, new: str, limit: int = 12) -> str:
    """Short human-readable diff: '+added words / -removed words'."""
    a, b = old.split(), new.split()
    added, removed = [], []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op in ("replace", "delete"):
            removed += a[i1:i2]
        if op in ("replace", "insert"):
            added += b[j1:j2]
    parts = []
    if added:
        parts.append("+" + " ".join(added[:limit]) + (" ..." if len(added) > limit else ""))
    if removed:
        parts.append("-" + " ".join(removed[:limit]) + (" ..." if len(removed) > limit else ""))
    return " / ".join(parts) or "whitespace or formatting only"


@dataclass
class Change:
    kind: str          # new | revised
    item: object
    version: int
    diff: str = ""


class State:
    """items: url -> record; health: source_id -> run health counters."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        data = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}
        self.items: dict[str, dict] = data.get("items", {})
        self.health: dict[str, dict] = data.get("health", {})

    def known_source(self, source_id: str) -> bool:
        return source_id in self.health and self.health[source_id].get("last_ok") is not None

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"items": dict(sorted(self.items.items())), "health": dict(sorted(self.health.items()))}
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def detect_changes(items, state: State, source, now: str) -> tuple[list[Change], int]:
    """Update state with this run's items. Returns (changes, baseline_count).

    The first successful run of a source records a baseline silently, so adding a
    source does not flood the digest with hundreds of "new" items.
    """
    baseline = not state.known_source(source.id)
    changes: list[Change] = []
    for item in items:
        digest = fingerprint(item, source.ignore)
        record = state.items.get(item.url)
        if record is None:
            state.items[item.url] = {
                "source": source.id, "title": item.title, "summary": item.summary,
                "published": item.published, "hash": digest, "version": 1,
                "first_seen": now, "last_seen": now, "last_changed": now,
            }
            if not baseline:
                changes.append(Change("new", item, 1))
            continue
        record["last_seen"] = now
        if record["hash"] != digest:
            old_text = f"{record['title']} {record.get('summary', '')}"
            diff = word_diff(old_text, f"{item.title} {item.summary}")
            record.update(title=item.title, summary=item.summary, published=item.published,
                          hash=digest, version=record["version"] + 1, last_changed=now)
            changes.append(Change("revised", item, record["version"], diff))
    return changes, (len(items) if baseline else 0)
