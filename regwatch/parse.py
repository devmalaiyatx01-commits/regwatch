"""Turn a fetched feed or listing page into a list of Items."""
from __future__ import annotations

import html
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


@dataclass
class Item:
    source_id: str
    url: str
    title: str
    published: str | None = None   # ISO 8601 date (YYYY-MM-DD)
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def clean_text(value: str | None) -> str:
    """Strip markup, decode entities, NFC-normalise and collapse whitespace."""
    if not value:
        return ""
    if "<" in value and ">" in value:
        value = BeautifulSoup(value, "html.parser").get_text(" ")
    value = html.unescape(value)
    value = unicodedata.normalize("NFC", value)
    value = value.replace("　", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def normalise_url(url: str, base: str = "") -> str:
    url = urljoin(base, url.strip())
    parts = urlsplit(url)
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                       if k not in TRACKING_PARAMS])
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, query, ""))


def parse_date(value: str | None, fmt: str = "") -> str | None:
    """Return YYYY-MM-DD for RFC 822, ISO 8601 or an explicit strptime format."""
    if not value:
        return None
    value = value.strip()
    dt = None
    if fmt:
        try:
            dt = datetime.strptime(value, fmt)
        except ValueError:
            dt = None
    if dt is None:
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            dt = None
    if dt is None:
        match = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", value)
        if match:
            try:
                dt = datetime(*map(int, match.groups()))
            except ValueError:
                dt = None
    if dt is None:
        return None
    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc)
    return dt.date().isoformat()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _child(el: ET.Element, *names: str) -> ET.Element | None:
    for child in el:
        if _local(child.tag) in names:
            return child
    return None


def _atom_link(entry: ET.Element) -> str:
    fallback = ""
    for child in entry:
        if _local(child.tag) == "link":
            href = child.get("href") or (child.text or "")
            if child.get("rel", "alternate") == "alternate":
                return href
            fallback = fallback or href
    return fallback


def parse_feed(body: bytes, source_id: str, base_url: str) -> list[Item]:
    """RSS 2.0 (<item>), RSS 1.0/RDF (<item> in a namespace) and Atom (<entry>)."""
    root = ET.fromstring(body.lstrip(b"\xef\xbb\xbf").strip())
    items: list[Item] = []
    for el in root.iter():
        name = _local(el.tag)
        if name not in ("item", "entry"):
            continue
        title_el = _child(el, "title")
        title = clean_text("".join(title_el.itertext()) if title_el is not None else "")
        link = _atom_link(el) if name == "entry" else ""
        if not link:
            link_el = _child(el, "link", "guid")
            link = (link_el.text or "").strip() if link_el is not None else ""
        if not link:
            link = el.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about", "")
        date_el = _child(el, "pubDate", "published", "updated", "date", "issued")
        summary_el = _child(el, "description", "summary", "content", "encoded")
        if not (title and link):
            continue
        items.append(Item(
            source_id=source_id,
            url=normalise_url(link, base_url),
            title=title,
            published=parse_date(date_el.text if date_el is not None else None),
            summary=clean_text("".join(summary_el.itertext()) if summary_el is not None else ""),
        ))
    return dedupe(items)


def parse_html(text: str, source, base_url: str) -> list[Item]:
    soup = BeautifulSoup(text, "html.parser")
    items: list[Item] = []
    for row in soup.select(source.row):
        parts = [clean_text(cell.get_text(" ")) for sel in source.title
                 for cell in row.select(sel)[:1]]
        title = " - ".join(p for p in parts if p)
        link_el = row.select_one(source.link)
        if not title or link_el is None or not link_el.get("href"):
            continue
        date_el = row.select_one(source.date) if source.date else None
        summary_el = row.select_one(source.summary) if source.summary else None
        items.append(Item(
            source_id=source.id,
            url=normalise_url(link_el["href"], base_url),
            title=title,
            published=parse_date(date_el.get_text(" ") if date_el else None, source.date_format),
            summary=clean_text(summary_el.get_text(" ")) if summary_el else "",
        ))
    return dedupe(items)


def dedupe(items: list[Item]) -> list[Item]:
    seen: set[str] = set()
    out = []
    for item in items:
        if item.url not in seen:
            seen.add(item.url)
            out.append(item)
    return out


def parse(source, result) -> list[Item]:
    if source.kind == "feed":
        return parse_feed(result.body, source.id, result.url)
    return parse_html(result.text(), source, result.url)
