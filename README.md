# RegWatch

Watches health authority websites for new and revised publications, classifies each one
(recall, safety alert, supply, enforcement, guidance, approval, other), scores how urgent it is,
and publishes a digest twice a day.

Live digest: https://devmalaiyatx01-commits.github.io/regwatch/

## What it covers

11 sources from 8 authorities, 4 languages, 5 formats:

| Source | Authority | Format | Fetch | Language | Scheduled cloud run |
|---|---|---|---|---|---|
| mhra-alerts, mhra-dsu | MHRA (UK) | Atom | HTTP | en | yes |
| ema-news | EMA (EU) | RSS 2.0 | HTTP | en | yes |
| hc-recalls | Health Canada | RSS 2.0 | HTTP | en | yes |
| ansm-news | ANSM (France) | RSS 2.0 | HTTP | fr | yes |
| aemps-news | AEMPS (Spain) | RSS 2.0 | HTTP | es | yes |
| pmda-ja, pmda-en | PMDA (Japan) | RSS 1.0 (RDF) | HTTP | ja, en | yes |
| openfda-drug-recalls | US FDA | JSON API (openFDA) | HTTP | en | yes |
| cdsco-notices | CDSCO (India) | HTML table, custom date format | HTTP | en | local runs |
| fda-recalls | US FDA | HTML table built by JavaScript | headless Chromium | en | local runs |

The FDA recalls page returns 404 to non-browser clients and fills its table from JavaScript, so it
is fetched with Playwright. Everything else uses plain HTTP, which is faster and cheaper.

## What the first cloud run found

Run locally (from India), all sources passed. The first scheduled run on GitHub's servers
(US datacenter IPs) passed 7 of 10 and showed three ways real sites refuse automated traffic:

| Source | What happened from the cloud | Response |
|---|---|---|
| FDA recalls page | bot protection never served the table to a cloud browser (timeout) | added the FDA's official **openFDA API** as a source for the cloud run; the page runs locally |
| CDSCO | connection refused from outside India | runs locally (`cloud = false`) |
| Health Canada | HTTP 429, too many requests | the fetcher now honours `Retry-After` and backs off 2, 4, 8 s |

RegWatch does not try to get around bot protection. Sources marked `cloud = false` are skipped by
the scheduled run and reported as "skipped", not as failures, and run from a machine the site accepts.

## How a run works

```
sources.toml
   |
   v
robots.txt check -> fetch (requests, or Playwright when fetch = "browser")
   |
   v
parse: RSS 2.0 / RSS 1.0 / Atom / CSS selectors / JSON templates -> Item(url, title, date, summary)
   |   strips markup, decodes entities, normalises Unicode, drops tracking parameters
   v
language detection (Unicode script + stopwords) -> en / fr / es / ja ...
   |
   v
change detection: SHA-256 of normalised text per URL -> new / revised / unchanged
   |   first run of a source is a silent baseline, so adding a source does not flood the digest
   v
classification: rules for everything; Claude for new and revised items when a key is set
   |
   v
state/state.json (committed, so git history is the audit log) + docs/index.html + reports/latest.md
```

## Run it

```bash
pip install -r requirements.txt
python -m playwright install chromium

python -m regwatch list                 # configured sources
python -m regwatch run                  # one monitoring run, writes docs/ and reports/
python -m regwatch run --llm            # same, Claude classifies new and revised items
python -m regwatch validate --all       # onboarding checks for every source
python -m regwatch eval                 # score the classifier on the labelled set
python -m pytest -q                     # 27 offline tests
```

`--llm` needs `ANTHROPIC_API_KEY`. Without it the rule classifier is used and nothing else changes.

## Adding a source

Add a `[[source]]` block to `sources.toml`, then run `python -m regwatch validate <id>`. The checks:
robots.txt allows it, HTTP 200, at least 3 items, absolute links, no duplicates, 80% of items dated,
titles in the configured language, titles not boilerplate. CI runs the same checks on every pull request.

## Classification

Every item gets a category, a severity (high, medium, low), a priority from 0 to 100 and a short reason.

* **Rules** (`regwatch/classify.py`): keyword lexicon in English, French, Spanish, German, Italian,
  Portuguese and Japanese. Free, fast and explainable. Used for the baseline and as the fallback.
* **Claude** (`claude-opus-5-5`, low effort, JSON schema output): runs only on new or revised items,
  which keeps cost proportional to what changed. It also returns an English title for non-English
  items. Scraped text is passed as untrusted data and the prompt tells the model not to follow
  instructions inside it. If the call fails, is refused, or returns a label outside the allowed set,
  the item falls back to the rules. If the rules saw something serious (a high-severity term, or a
  recall) that the model downplayed, the item is flagged for review instead of silently trusted.

## Evaluation

`evals/labelled.jsonl` has 124 real publications from the first run, labelled by hand
(guide: `evals/LABELLING.md`). The rule lexicon was tuned on the dev split only. Results on the
held-out test split (49 items), from `python -m regwatch eval`:

| Metric | Rules |
|---|---:|
| Category accuracy | 85.7% |
| Category macro-F1 | 0.817 |
| Severity accuracy | 91.8% |
| Recall on high-severity items | 100% |

Full per-language and per-class breakdown, and every miss, in `evals/results.md`. The misses are
typical keyword failures, for example "un-approved drug products" matching the approval stem. The
Claude path is covered by unit tests with a stubbed client; run `python -m regwatch eval --llm`
with a key to score it on the same split.

## Scheduling and monitoring

`.github/workflows/monitor.yml` runs at 07:00 and 19:00 IST with `REGWATCH_CLOUD=1` (which skips
the `cloud = false` sources). Each run commits the updated state,
digest and report. Per source it records status, item count, new and revised counts, latency and
the error if any. A source that errors or suddenly parses 0 items (a sign the page layout changed)
twice in a row fails the workflow, which emails the repository owner.

## Limitations and next steps

* Only titles and listing summaries are compared. Fetching and diffing each detail page (and PDF
  attachments) would catch silent edits to the body text.
* Language detection is tuned for short titles in the languages above.
* Next sources worth adding: TGA (Australia), Swissmedic (de/fr/it), BfArM (de), NMPA (zh).
