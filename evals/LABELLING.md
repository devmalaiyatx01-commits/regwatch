# Labelling guide

`labelled.jsonl` holds 124 real publications collected by the first monitoring run on 2026-11-19,
labelled by hand with one category and one severity.

## Splits

* `dev` (75 items): the 9 most recent items per source. The rule lexicon was tuned while looking at these.
* `test` (49 items): items 10 to 17 per source. Labelled from title and summary only, without looking at
  any classifier output, and never used for tuning. Report this split.

## Categories

| Category | Use when |
|---|---|
| recall | a product recall or batch or market withdrawal |
| safety_alert | new safety information: warnings, label or prescribing changes, safety reviews, field safety notices, quality defects, and suspensions or restrictions made for safety reasons |
| supply | shortages, supply disruption, discontinuation |
| enforcement | action against a company or product for non-compliance: warning letters, cancelled licences, falsified or unapproved products, misleading claims |
| guidance | guidelines, rules, consultations, circulars, procedural or pharmacopoeia updates |
| approval | authorisations, approvals, positive opinions, committee meetings that decide approvals |
| other | events, campaigns, corporate news, bulletins, administrative notices |

## Severity

* **high**: patient harm is likely or immediate action is needed (class 1 recalls, deaths, pathogen
  contamination, falsified medicines in the supply chain, authorisation withdrawn or suspended for safety).
* **medium**: a regulatory professional should act on or review it (class 2 recalls, new warnings,
  enforcement actions, new guidance, supply problems).
* **low**: informational (class 3 and 4 notices, approvals lists, meetings, events, bulletins).
