"""Command line: python -m regwatch {run,validate,eval,list}"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from .classify import LLMClassifier, RuleClassifier
from .config import load_sources
from .detect import State


def pick_classifier(use_llm: bool):
    if use_llm and os.environ.get("ANTHROPIC_API_KEY"):
        return LLMClassifier()
    if use_llm:
        logging.warning("--llm given but ANTHROPIC_API_KEY is not set; using rules")
    return RuleClassifier()


def cmd_run(args) -> int:
    from .pipeline import run
    from .report import write_reports

    sources = load_sources(args.sources)
    if args.only:
        wanted = set(args.only.split(","))
        sources = [s for s in sources if s.id in wanted]
    state = State(args.state)
    report = run(sources, state, pick_classifier(args.llm))
    state.save()
    write_reports(report, state, sources, args.out, args.markdown)
    print(f"{len(report.changes)} changes; {sum(s.status == 'ok' for s in report.sources)}/"
          f"{len(report.sources)} sources ok")
    for s in report.sources:
        flag = "DEGRADED" if s.degraded else s.status
        print(f"  {s.source_id:15} {flag:8} items={s.items:<4} new={s.new:<3} revised={s.revised:<3} "
              f"{s.elapsed_ms:>6} ms {s.error[:70]}")
    if report.llm_usage:
        print("  llm usage:", json.dumps(report.llm_usage))
    # Non-zero exit makes the scheduled GitHub Action fail, which emails the repo owner.
    return 2 if report.degraded else 0


def cmd_validate(args) -> int:
    from .validate import validate_source

    sources = load_sources(args.sources)
    chosen = sources if args.all else [s for s in sources if s.id in args.ids]
    if not chosen:
        print("no matching sources; ids:", ", ".join(s.id for s in sources))
        return 1
    failed = 0
    for source in chosen:
        print(f"\n{source.id} ({source.url})")
        for name, ok, detail in validate_source(source):
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))
            failed += not ok
    return 1 if failed else 0


def cmd_eval(args) -> int:
    from .evaluate import evaluate, load_labelled, to_markdown

    rows = load_labelled(args.data)
    splits = sorted({r.get("split", "all") for r in rows}, key=lambda s: s != "test")
    classifiers = [("Rule classifier", RuleClassifier())]
    if args.llm:
        clf = pick_classifier(True)
        if isinstance(clf, LLMClassifier):
            classifiers.append((f"LLM classifier ({clf.model})", clf))
    out = []
    for name, clf in classifiers:
        for split in splits:
            subset = [r for r in rows if r.get("split", "all") == split]
            out.append(to_markdown(f"{name}, {split} split", evaluate(clf, subset)))
        if isinstance(clf, LLMClassifier):
            out.append(f"LLM usage: {json.dumps(clf.usage)}\n")
    text = "\n".join(out)
    print(text)
    if args.write:
        with open(args.write, "w", encoding="utf-8") as fh:
            fh.write("# Classifier evaluation\n\n" + text)
    return 0


def cmd_list(args) -> int:
    for s in load_sources(args.sources):
        print(f"{s.id:15} {s.kind:5} {s.fetch:8} {s.lang}  {s.authority:15} {s.url}")
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # Windows consoles default to cp1252
    parser = argparse.ArgumentParser(prog="regwatch")
    parser.add_argument("--sources", default="sources.toml")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("run", help="fetch all sources, detect changes, classify, write the digest")
    p.add_argument("--state", default="state/state.json")
    p.add_argument("--out", default="docs")
    p.add_argument("--markdown", default="reports/latest.md")
    p.add_argument("--only", help="comma-separated source ids")
    p.add_argument("--llm", action="store_true", help="classify changed items with Claude")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("validate", help="onboarding checks for sources")
    p.add_argument("ids", nargs="*")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("eval", help="score classifiers on the labelled set")
    p.add_argument("--data", default="evals/labelled.jsonl")
    p.add_argument("--llm", action="store_true")
    p.add_argument("--write", help="also write the results to this Markdown file")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("list", help="show configured sources")
    p.set_defaults(func=cmd_list)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
