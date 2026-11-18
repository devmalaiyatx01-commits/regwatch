"""Write the run digest as Markdown (for people and git diffs) and HTML (for GitHub Pages)."""
from __future__ import annotations

import html
from datetime import date, timedelta
from pathlib import Path

from .pipeline import RunReport

LANG_NAMES = {"en": "English", "fr": "French", "es": "Spanish", "ja": "Japanese", "de": "German"}


def watchlist(state, days: int = 45, limit: int = 60) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    rows = [{**rec, "url": url} for url, rec in state.items.items()
            if "category" in rec and (rec.get("published") or rec["first_seen"][:10]) >= cutoff]
    rows.sort(key=lambda r: r.get("published") or "", reverse=True)   # newest first...
    rows.sort(key=lambda r: -r["priority"])                           # ...within each priority
    return rows[:limit]


def to_markdown(report: RunReport, state) -> str:
    lines = [f"# RegWatch digest, run {report.started}", ""]
    lines.append(f"{len(report.changes)} new or revised publications across {len(report.sources)} sources.")
    if report.degraded:
        lines.append("")
        lines.append("**Degraded sources:** " + ", ".join(f"{s.source_id} ({s.error})" for s in report.degraded))
    lines += ["", "## Changes this run", ""]
    if report.changes:
        lines.append("| Priority | Change | Category | Severity | Lang | Authority | Title |")
        lines.append("|---:|---|---|---|---|---|---|")
        for c in report.changes:
            title = c.get("english_title") or c["title"]
            lines.append(f"| {c['priority']} | {c['change']} | {c['category']} | {c['severity']} | "
                         f"{c['lang']} | {c['authority']} | [{title.replace('|', '/')}]({c['url']}) |")
    else:
        lines.append("No new or revised publications.")
    lines += ["", "## Source health", "", "| Source | Status | Items | New | Revised | Time (ms) | Via | Error |",
              "|---|---|---:|---:|---:|---:|---|---|"]
    for s in report.sources:
        lines.append(f"| {s.source_id} | {s.status} | {s.items} | {s.new} | {s.revised} | "
                     f"{s.elapsed_ms} | {s.via} | {s.error[:80]} |")
    return "\n".join(lines) + "\n"


CSS = """
:root{--bg:#f7f6f3;--fg:#1d1d1b;--muted:#6b6a66;--line:#dedbd4;--high:#b3261e;--med:#b26a00;--low:#4a6b48}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe7;--muted:#a3a19b;--line:#33322f}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:32px 16px}
h1{font-size:28px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 8px}
p.meta{color:var(--muted);margin:0 0 16px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums}
a{color:inherit}
.sev{font-weight:600}.sev.high{color:var(--high)}.sev.medium{color:var(--med)}.sev.low{color:var(--low)}
.orig{color:var(--muted);font-size:13px}.why{color:var(--muted);font-size:12px}
.wrap{overflow-x:auto}
"""


def _row(c: dict, show_change: bool) -> str:
    title = c.get("english_title") or c["title"]
    orig = f'<div class="orig">{html.escape(c["title"])}</div>' if c.get("english_title") and c["english_title"] != c["title"] else ""
    change = f"<td>{html.escape(c['change'])}</td>" if show_change else ""
    review = " (review)" if c.get("needs_review") else ""
    return (f"<tr><td class='num'>{c['priority']}</td>{change}<td>{c['category']}</td>"
            f"<td class='sev {c['severity']}'>{c['severity']}{review}</td><td>{c['lang']}</td>"
            f"<td>{html.escape(c.get('authority', c['source']))}</td>"
            f"<td><a href='{html.escape(c['url'])}'>{html.escape(title)}</a>{orig}"
            f"<div class='why'>{html.escape(c['reasoning'])}</div></td>"
            f"<td>{c.get('published') or ''}</td></tr>")


def to_html(report: RunReport, state, authorities: dict[str, str]) -> str:
    langs = sorted({rec.get("lang", "") for rec in state.items.values()} - {""})
    head = ("<tr><th>Priority</th>{}<th>Category</th><th>Severity</th><th>Lang</th>"
            "<th>Authority</th><th>Publication</th><th>Date</th></tr>")
    changes = "".join(_row(c, True) for c in report.changes) or \
        "<tr><td colspan='8'>No new or revised publications in this run.</td></tr>"
    watch = []
    for rec in watchlist(state):
        rec = {**rec, "authority": authorities.get(rec["source"], rec["source"])}
        watch.append(_row(rec, False))
    health = "".join(
        f"<tr><td>{s.source_id}</td><td>{html.escape(s.authority)}</td><td>{s.status}</td>"
        f"<td class='num'>{s.items}</td><td class='num'>{s.new}</td><td class='num'>{s.revised}</td>"
        f"<td class='num'>{s.elapsed_ms}</td><td>{s.via}</td><td>{html.escape(s.error[:120])}</td></tr>"
        for s in report.sources)
    lang_text = ", ".join(LANG_NAMES.get(code, code) for code in langs)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RegWatch digest</title><style>{CSS}</style></head><body><main>
<h1>RegWatch digest</h1>
<p class="meta">Run {report.started} UTC. {len(report.sources)} sources, {len(state.items)} publications tracked, languages: {lang_text}.
Source code: <a href="https://github.com/devmalaiyatx01-commits/regwatch">github.com/devmalaiyatx01-commits/regwatch</a></p>
<h2>Changes this run</h2><div class="wrap"><table>{head.format('<th>Change</th>')}{changes}</table></div>
<h2>Watchlist, last 45 days by priority</h2><div class="wrap"><table>{head.format('')}{''.join(watch)}</table></div>
<h2>Source health</h2><div class="wrap"><table><tr><th>Source</th><th>Authority</th><th>Status</th><th>Items</th>
<th>New</th><th>Revised</th><th>ms</th><th>Via</th><th>Error</th></tr>{health}</table></div>
</main></body></html>
"""


def write_reports(report: RunReport, state, sources, out_dir: str = "docs", md_path: str = "reports/latest.md") -> None:
    authorities = {s.id: s.authority for s in sources}
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(out_dir, "index.html").write_text(to_html(report, state, authorities), encoding="utf-8")
    Path(md_path).parent.mkdir(parents=True, exist_ok=True)
    Path(md_path).write_text(to_markdown(report, state), encoding="utf-8")
