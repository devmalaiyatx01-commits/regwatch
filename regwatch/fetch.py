"""Download a source over plain HTTP or through a headless browser."""
from __future__ import annotations

import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests

USER_AGENT = "RegWatch/0.1 (+https://github.com/devmalaiyatx01-commits/regwatch)"
TIMEOUT = 30
RETRY_STATUS = {429, 500, 502, 503, 504}

_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


@dataclass
class FetchResult:
    url: str
    status: int
    body: bytes
    content_type: str
    elapsed_ms: int
    via: str

    def text(self) -> str:
        """Decode HTML. XML is passed as bytes so the parser reads the encoding declaration."""
        charset = None
        if "charset=" in self.content_type:
            charset = self.content_type.split("charset=")[-1].split(";")[0].strip()
        for enc in filter(None, (charset, "utf-8")):
            try:
                return self.body.decode(enc)
            except (LookupError, UnicodeDecodeError):
                continue
        return self.body.decode("utf-8", errors="replace")


class FetchError(Exception):
    pass


def allowed_by_robots(url: str, session: requests.Session | None = None) -> bool:
    parts = urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    if root not in _robots_cache:
        parser = urllib.robotparser.RobotFileParser()
        try:
            resp = (session or requests).get(f"{root}/robots.txt", timeout=15,
                                              headers={"User-Agent": USER_AGENT})
            if resp.status_code == 200 and "text/plain" in resp.headers.get("content-type", ""):
                parser.parse(resp.text.splitlines())
                _robots_cache[root] = parser
            else:
                _robots_cache[root] = None  # no usable robots.txt: allowed
        except requests.RequestException:
            _robots_cache[root] = None
    parser = _robots_cache[root]
    return parser is None or parser.can_fetch(USER_AGENT, url)


def fetch_http(url: str, retries: int = 2, session: requests.Session | None = None) -> FetchResult:
    session = session or requests.Session()
    last_error = ""
    for attempt in range(retries + 1):
        start = time.monotonic()
        try:
            resp = session.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
        except requests.RequestException as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        else:
            elapsed = int((time.monotonic() - start) * 1000)
            if resp.status_code not in RETRY_STATUS:
                return FetchResult(resp.url, resp.status_code, resp.content,
                                   resp.headers.get("content-type", ""), elapsed, "http")
            last_error = f"HTTP {resp.status_code}"
        if attempt < retries:
            time.sleep(2 ** attempt)
    raise FetchError(last_error)


def fetch_browser(url: str, wait_for: str = "", timeout_ms: int = 45_000) -> FetchResult:
    """Render the page in headless Chromium and return the final DOM."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # optional dependency
        raise FetchError("playwright not installed: pip install playwright && "
                         "python -m playwright install chromium") from exc
    start = time.monotonic()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            if wait_for:
                page.wait_for_selector(wait_for, timeout=timeout_ms)
            html = page.content()
            status = resp.status if resp else 0
        except Exception as exc:  # playwright raises its own error types
            raise FetchError(f"{type(exc).__name__}: {exc}") from exc
        finally:
            browser.close()
    elapsed = int((time.monotonic() - start) * 1000)
    return FetchResult(url, status, html.encode("utf-8"), "text/html; charset=utf-8", elapsed, "browser")


def fetch(source, session: requests.Session | None = None) -> FetchResult:
    if source.fetch == "browser":
        return fetch_browser(source.url, source.wait_for)
    return fetch_http(source.url, session=session)
