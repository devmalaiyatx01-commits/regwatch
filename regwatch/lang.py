"""Small, dependency-free language identification for short regulatory titles.

Two signals:
1. Unicode script. Kana means Japanese, Hangul Korean, Han without kana Chinese,
   Cyrillic Russian, and so on. This is reliable even for 5-word titles.
2. For Latin-script text, stopword hits plus a few diacritics that are strong hints.
"""
from __future__ import annotations

import re
import unicodedata

SCRIPT_RANGES = {
    "kana": [(0x3040, 0x30FF), (0x31F0, 0x31FF), (0xFF66, 0xFF9F)],
    "han": [(0x4E00, 0x9FFF), (0x3400, 0x4DBF)],
    "hangul": [(0xAC00, 0xD7AF), (0x1100, 0x11FF)],
    "cyrillic": [(0x0400, 0x04FF)],
    "arabic": [(0x0600, 0x06FF)],
    "devanagari": [(0x0900, 0x097F)],
    "greek": [(0x0370, 0x03FF)],
}

STOPWORDS = {
    "en": "the of and to for in on with from by is are new safety update recall medicines products".split(),
    "fr": ("le la les des du de et en l d à au aux par pour sur dans avec une un est sont qui "
           "nouvelles médicaments sécurité rappel").split(),
    "es": ("el la los las del de y en al se que su sus para por con una un unos unas es son sobre "
           "nota informativa medicamentos seguridad retirada").split(),
    "de": "der die das und für mit von zu im den des ist sind eine ein arzneimittel sicherheit rückruf".split(),
    "it": "il lo la gli le dei del di della e per con una un è sono sulla farmaci sicurezza".split(),
    "pt": "o a os as de do da dos das e em no na para com uma um é são sobre medicamentos segurança".split(),
    "nl": "de het een en van voor met op is zijn geneesmiddelen veiligheid".split(),
}
DIACRITIC_HINTS = {"fr": "éèêàçœûô", "es": "ñ¿¡ó", "de": "äöüß", "pt": "ãõ", "it": "ìò"}
# Word endings that are typical for one language (+0.5 per word).
SUFFIX_HINTS = {"es": ("ción", "ciones"), "pt": ("ção", "ções"), "it": ("zione", "zioni"),
                "fr": ("eaux", "ière", "ées"), "de": ("ung", "keit", "heit")}


def script_counts(text: str) -> dict[str, int]:
    counts = {"latin": 0, **{k: 0 for k in SCRIPT_RANGES}}
    for ch in text:
        cp = ord(ch)
        for script, ranges in SCRIPT_RANGES.items():
            if any(lo <= cp <= hi for lo, hi in ranges):
                counts[script] += 1
                break
        else:
            if ch.isalpha() and unicodedata.name(ch, "").startswith("LATIN"):
                counts["latin"] += 1
    return counts


def detect_language(text: str) -> tuple[str, float]:
    """Return (ISO 639-1 code or 'und', confidence 0..1)."""
    counts = script_counts(text)
    letters = sum(counts.values())
    if not letters:
        return "und", 0.0
    cjk = counts["kana"] + counts["han"]
    if cjk / letters > 0.2:
        if counts["kana"]:
            return "ja", round(cjk / letters, 2)
        # Han characters only: Japanese titles can be all kanji, so this is ambiguous.
        # Low confidence lets the caller fall back to the source's configured language.
        return "zh", 0.25
    for script, code in (("hangul", "ko"), ("cyrillic", "ru"), ("arabic", "ar"),
                         ("devanagari", "hi"), ("greek", "el")):
        if counts[script] / letters > 0.3:
            return code, round(counts[script] / letters, 2)

    words = re.findall(r"[^\W\d_]+", text.lower())
    if not words:
        return "und", 0.0
    scores = {lang: sum(w in stop for w in words) for lang, stop in
              ((lang, set(sw)) for lang, sw in STOPWORDS.items())}
    lowered = text.lower()
    for lang, marks in DIACRITIC_HINTS.items():
        if any(m in lowered for m in marks):
            scores[lang] += 1.5
    for lang, endings in SUFFIX_HINTS.items():
        scores[lang] += 0.5 * sum(w.endswith(endings) for w in words)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "und", 0.0
    total = sum(scores.values())
    return best, round(scores[best] / total, 2)
