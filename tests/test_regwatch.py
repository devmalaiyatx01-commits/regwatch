"""Offline tests: no network, no API key."""
import json
from types import SimpleNamespace

import pytest

from regwatch.classify import LLMClassifier, RuleClassifier
from regwatch.config import Source, check_source
from regwatch.detect import State, detect_changes, fingerprint
from regwatch.lang import detect_language
from regwatch.parse import Item, normalise_url, parse_date, parse_feed, parse_html

ATOM = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
 <entry><title>Class 2 Medicines Recall: Example Ltd</title>
  <link rel="alternate" href="https://www.gov.uk/drug-device-alerts/x?utm_source=feed"/>
  <updated>2026-11-05T10:00:00+00:00</updated><summary>Batch recall.</summary></entry>
</feed>"""

RSS2 = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>
 <item><title>Rappel de lots : Exemple 20 mg</title><link>https://ansm.sante.fr/a</link>
  <pubDate>Wed, 18 Nov 2026 09:00:00 +0100</pubDate><description><![CDATA[<p>Publi&eacute; le 18/11/2026</p>]]></description></item>
</channel></rss>""".encode("utf-8")

RDF = """<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns="http://purl.org/rss/1.0/" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:dc="http://purl.org/dc/elements/1.1/">
 <item rdf:about="https://www.pmda.go.jp/x.html"><title>[PMDA]回収情報を掲載しました</title>
  <link>https://www.pmda.go.jp/x.html</link><dc:date>2026-11-06T09:00:00+09:00</dc:date></item>
</rdf:RDF>""".encode("utf-8")

HTML_TABLE = """<table id="example"><tbody>
<tr><td>1</td><td>Cancellation of Import permission for M/s Example</td><td>2026-Nov-11</td>
<td><a href="/download.jsp?num_id=MTQ4">pdf</a></td></tr>
<tr><td>2</td><td>Draft Guidance document for IVD manufacturers</td><td>2026-Oct-09</td>
<td><a href="/download.jsp?num_id=MTQ5">pdf</a></td></tr></tbody></table>"""


def test_parse_atom_rss_and_rdf():
    atom = parse_feed(ATOM, "mhra", "https://www.gov.uk/")
    assert atom[0].url == "https://www.gov.uk/drug-device-alerts/x"     # tracking param dropped
    assert atom[0].published == "2026-11-05"
    rss = parse_feed(RSS2, "ansm", "https://ansm.sante.fr/")
    assert rss[0].summary == "Publié le 18/11/2026"                      # markup and entities removed
    assert rss[0].published == "2026-11-18"
    rdf = parse_feed(RDF, "pmda", "https://www.pmda.go.jp/")
    assert rdf[0].title.startswith("[PMDA]回収") and rdf[0].published == "2026-11-06"


def test_parse_html_table_with_custom_date_format():
    src = Source(id="cdsco", authority="CDSCO", url="https://cdsco.gov.in/x/", kind="html",
                 row="table#example tbody tr", title=("td:nth-of-type(2)",),
                 link="td:nth-of-type(4) a", date="td:nth-of-type(3)", date_format="%Y-%b-%d")
    items = parse_html(HTML_TABLE, src, "https://cdsco.gov.in/x/")
    assert [i.published for i in items] == ["2026-11-11", "2026-10-09"]
    assert items[0].url == "https://cdsco.gov.in/download.jsp?num_id=MTQ4"


def test_parse_date_variants():
    assert parse_date("Tue, 17 Nov 2026 23:30:00 -0500") == "2026-11-18"   # normalised to UTC
    assert parse_date("2026-11-05T10:00:00Z") == "2026-11-05"
    assert parse_date("11/18/2026", "%m/%d/%Y") == "2026-11-18"
    assert parse_date("Fecha: 2026.11.03") == "2026-11-03"
    assert parse_date("no date here") is None


def test_normalise_url_keeps_meaningful_query():
    assert normalise_url("/a?num_id=5&utm_campaign=x#top", "https://X.org/") == "https://x.org/a?num_id=5"


@pytest.mark.parametrize("text,lang", [
    ("Class 2 Medicines Recall: Accord-UK Ltd, Lercanidipine tablets", "en"),
    ("Tensions en furosémide : l'ANSM met en place de nouvelles mesures", "fr"),
    ("La AEMPS informa de un riesgo en ciertos sistemas de elevación", "es"),
    ("[PMDA]専門委員名簿を更新しました", "ja"),
])
def test_detect_language(text, lang):
    assert detect_language(text)[0] == lang


def test_han_only_text_is_low_confidence():
    lang, confidence = detect_language("法人文書開示請求書等様式")
    assert confidence < 0.3   # caller falls back to the source language


def test_change_detection_new_revised_and_noise():
    src = Source(id="s", authority="A", url="https://a.org/feed", ignore=(r"Mis à jour le \S+",))
    state = State("unused.json")
    first = [Item("s", "https://a.org/1", "Rappel de lots X", "2026-11-01", "Mis à jour le 01/11/2026")]
    changes, baseline = detect_changes(first, state, src, "t1")
    assert changes == [] and baseline == 1                       # first run is a silent baseline
    state.health["s"] = {"last_ok": "t1"}                         # what the pipeline records
    # Only the ignored "updated" stamp changes: not a revision.
    noisy = [Item("s", "https://a.org/1", "Rappel  de lots X", "2026-11-01", "Mis à jour le 02/11/2026")]
    assert detect_changes(noisy, state, src, "t2")[0] == []
    revised = [Item("s", "https://a.org/1", "Rappel de lots X et Y", "2026-11-01", ""),
               Item("s", "https://a.org/2", "Nouvelle alerte", "2026-11-03", "")]
    changes, _ = detect_changes(revised, state, src, "t3")
    kinds = {c.item.url: (c.kind, c.version) for c in changes}
    assert kinds == {"https://a.org/1": ("revised", 2), "https://a.org/2": ("new", 1)}
    assert "+et Y" in changes[0].diff or "+et Y" in changes[1].diff


def test_fingerprint_ignores_unicode_width_and_spacing():
    a = Item("s", "u", "ＰＭＤＡ：回収 　情報", None, "")    # full-width letters, ideographic space
    b = Item("s", "u", "PMDA:回収 情報", None, "")
    assert fingerprint(a) == fingerprint(b)
    assert fingerprint(a) != fingerprint(Item("s", "u", "PMDA:回収 情報 更新", None, ""))


@pytest.mark.parametrize("title,summary,category,severity", [
    ("Class 2 Medicines Recall: Advanz Pharma", "", "recall", "medium"),
    ("Sandwich", "Potential to be contaminated with Listeria monocytogenes.", "other->recall", "high"),
    ("Class 4 Medicines Defect Notification: Sandoz, powder for oral suspension", "", "safety_alert", "low"),
    ("FDA warning letter to Example Inc", "", "enforcement", "medium"),
    ("Tensions en furosémide 20 et 40 mg", "", "supply", "medium"),
    ("PMDA-ATC Pharmacovigilance Seminar 2027 applications open", "", "other", "low"),
    ("Duvyzat: interim advice following reports of deaths", "", "safety_alert", "high"),
    ("[PMDA]自主回収のお知らせ", "", "recall", "medium"),
])
def test_rule_classifier(title, summary, category, severity):
    hint = "recall" if category == "other->recall" else ""
    result = RuleClassifier().classify(title, summary, hint=hint)
    assert result.category == category.split("->")[-1]
    assert result.severity == severity
    assert 0 <= result.priority <= 100 and result.reasoning


def test_check_source_rejects_bad_config():
    bad = Source(id="x", authority="A", url="ftp://x", kind="html", fetch="curl")
    assert len(check_source(bad)) == 3


class FakeClient:
    """Stands in for anthropic.Anthropic(); returns a canned response."""

    def __init__(self, text, stop_reason="end_turn"):
        response = SimpleNamespace(
            stop_reason=stop_reason,
            content=[SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(input_tokens=120, output_tokens=40))
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=lambda **kw: response))


def test_llm_classifier_happy_path_and_review_flag():
    payload = json.dumps({"category": "recall", "severity": "medium", "priority": 140,
                          "english_title": "Batch recall", "reasoning": "says recall"})
    clf = LLMClassifier(client=FakeClient(payload))
    result = clf.classify("Rappel de lots", "contamination par Listeria", lang="fr")
    assert result.method == "llm" and result.priority == 100          # clamped
    assert result.needs_review                                       # rules saw 'high', model said medium
    assert clf.usage["input_tokens"] == 120


@pytest.mark.parametrize("text,stop", [("not json", "end_turn"),
                                       ('{"category": "made_up", "severity": "low", "priority": 1, '
                                        '"english_title": "", "reasoning": ""}', "end_turn"),
                                       ("{}", "refusal")])
def test_llm_classifier_falls_back_to_rules(text, stop):
    clf = LLMClassifier(client=FakeClient(text, stop))
    result = clf.classify("Class 2 Medicines Recall: Example")
    assert result.method == "rules_fallback" and result.category == "recall"
    assert clf.usage["fallbacks"] == 1
