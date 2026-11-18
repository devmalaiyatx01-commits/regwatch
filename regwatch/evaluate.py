"""Score a classifier against the hand-labelled set in evals/labelled.jsonl."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from .classify import CATEGORIES


def load_labelled(path: str | Path = "evals/labelled.jsonl") -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def f1_per_class(pairs: list[tuple[str, str]], labels: list[str]) -> dict[str, float]:
    scores = {}
    for label in labels:
        tp = sum(1 for g, p in pairs if g == label and p == label)
        fp = sum(1 for g, p in pairs if g != label and p == label)
        fn = sum(1 for g, p in pairs if g == label and p != label)
        if tp + fp + fn == 0:
            continue
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores[label] = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return scores


def evaluate(classifier, rows: list[dict]) -> dict:
    preds = []
    for row in rows:
        result = classifier.classify(row["title"], row.get("summary", ""), hint=row.get("hint", ""),
                                     authority=row.get("authority", ""), lang=row.get("lang", ""))
        preds.append(result)
    cat_pairs = [(r["category"], p.category) for r, p in zip(rows, preds)]
    sev_pairs = [(r["severity"], p.severity) for r, p in zip(rows, preds)]
    by_lang: dict[str, list[bool]] = defaultdict(list)
    for r, p in zip(rows, preds):
        by_lang[r["lang"]].append(r["category"] == p.category)
    f1 = f1_per_class(cat_pairs, CATEGORIES)
    high_gold = [p.severity == "high" for r, p in zip(rows, preds) if r["severity"] == "high"]
    return {
        "n": len(rows),
        "category_accuracy": sum(g == p for g, p in cat_pairs) / len(rows),
        "category_macro_f1": sum(f1.values()) / len(f1),
        "severity_accuracy": sum(g == p for g, p in sev_pairs) / len(rows),
        "high_severity_recall": sum(high_gold) / len(high_gold) if high_gold else None,
        "per_class_f1": f1,
        "per_language_accuracy": {k: (sum(v) / len(v), len(v)) for k, v in sorted(by_lang.items())},
        "confusion": Counter(cat_pairs),
        "errors": [(r["title"], r["category"], p.category, r["severity"], p.severity)
                   for r, p in zip(rows, preds) if r["category"] != p.category or r["severity"] != p.severity],
    }


def to_markdown(name: str, m: dict) -> str:
    pct = lambda x: f"{100 * x:.1f}%"
    lines = [f"## {name} ({m['n']} labelled publications)", "",
             "| Metric | Value |", "|---|---:|",
             f"| Category accuracy | {pct(m['category_accuracy'])} |",
             f"| Category macro-F1 | {m['category_macro_f1']:.3f} |",
             f"| Severity accuracy | {pct(m['severity_accuracy'])} |",
             f"| Recall on high-severity items | {pct(m['high_severity_recall']) if m['high_severity_recall'] is not None else 'n/a'} |",
             "", "| Language | Category accuracy | Items |", "|---|---:|---:|"]
    for lang, (acc, n) in m["per_language_accuracy"].items():
        lines.append(f"| {lang} | {pct(acc)} | {n} |")
    lines += ["", "| Category | F1 |", "|---|---:|"]
    for cat, score in m["per_class_f1"].items():
        lines.append(f"| {cat} | {score:.2f} |")
    if m["errors"]:
        lines += ["", "Misses (title / gold category / predicted / gold severity / predicted):", ""]
        for title, g, p, gs, ps in m["errors"]:
            lines.append(f"- {title[:90]} : {g} -> {p}, {gs} -> {ps}")
    return "\n".join(lines) + "\n"
