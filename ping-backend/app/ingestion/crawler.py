"""Fetching customer web pages and sitemaps, safely.

Every URL here is user-supplied and fetched from Ping's servers, which makes
it an SSRF vector: a sitemap could point at http://169.254.169.254/ or an
internal service. Each request (and each redirect hop) is checked against
private, loopback, link-local and reserved addresses before it is made.
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from defusedxml import ElementTree

from app.core import netguard
from app.core.config import get_settings
from app.core.errors import ValidationError
from app.ingestion.html import Page, html_to_markdown

log = logging.getLogger(__name__)

_MIN_WORDS = 30


class CrawlError(Exception):
    pass


@dataclass
class FetchedPage:
    url: str
    page: Page


def normalize_url(raw: str) -> str:
    url = raw.strip()
    if not url:
        raise ValidationError("Enter a URL")
    if "://" not in url:
        url = "https://" + url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValidationError("Enter a valid http(s) URL")
    return parsed._replace(fragment="").geturl()


def _check_host(url: str) -> None:
    reason = netguard.private_host_reason(url)
    if reason:
        raise CrawlError(reason if reason.startswith("Could not") else f"{reason} and cannot be crawled")


def _client() -> httpx.Client:
    settings = get_settings()
    return httpx.Client(
        timeout=settings.crawl_timeout_seconds,
        headers={"User-Agent": settings.crawl_user_agent, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.5"},
        follow_redirects=False,
    )


def fetch(url: str, max_redirects: int = 5) -> httpx.Response:
    """GET with the SSRF check on every hop and a hard size cap."""
    settings = get_settings()
    with _client() as client:
        for _ in range(max_redirects + 1):
            _check_host(url)
            try:
                with client.stream("GET", url) as response:
                    if response.is_redirect:
                        url = urljoin(url, response.headers.get("location", ""))
                        continue
                    if response.status_code >= 400:
                        raise CrawlError(f"{url} returned HTTP {response.status_code}")
                    body = b""
                    for chunk in response.iter_bytes():
                        body += chunk
                        if len(body) > settings.crawl_max_page_bytes:
                            raise CrawlError(f"{url} is larger than the page size limit")
                    return httpx.Response(
                        response.status_code, headers=response.headers, content=body,
                        request=response.request,
                    )
            except httpx.HTTPError as exc:
                raise CrawlError(f"Could not fetch {url}: {exc.__class__.__name__}") from exc
    raise CrawlError(f"{url} redirected too many times")


def fetch_page(url: str) -> FetchedPage:
    response = fetch(url)
    ctype = response.headers.get("content-type", "")
    if "html" not in ctype and "xml" not in ctype and ctype:
        raise CrawlError(f"{url} is not an HTML page ({ctype.split(';')[0]})")
    page = html_to_markdown(response.text, fallback_title=urlparse(url).path or url)
    if page.word_count < _MIN_WORDS:
        raise CrawlError("No readable content was found on this page.")
    return FetchedPage(url=str(response.request.url) if response.request else url, page=page)


def sitemap_urls(sitemap_url: str, limit: int, _depth: int = 0) -> list[str]:
    """Page URLs from a sitemap or sitemap index (one level of nesting)."""
    response = fetch(sitemap_url)
    try:
        root = ElementTree.fromstring(response.content)
    except ElementTree.ParseError as exc:
        raise CrawlError("The sitemap is not valid XML") from exc

    def locs(tag: str) -> list[str]:
        return [
            el.text.strip()
            for el in root.iter()
            if el.tag.endswith(tag) and el.text and el.text.strip()
        ]

    urls: list[str] = []
    if root.tag.endswith("sitemapindex"):
        if _depth >= 1:
            return []
        for child in [u for u in locs("loc")]:
            try:
                urls.extend(sitemap_urls(child, limit - len(urls), _depth + 1))
            except CrawlError as exc:
                log.warning("skipping nested sitemap %s: %s", child, exc)
            if len(urls) >= limit:
                break
    else:
        urls = locs("loc")

    seen: set[str] = set()
    out = []
    for u in urls:
        if u not in seen and u.startswith(("http://", "https://")):
            seen.add(u)
            out.append(u)
        if len(out) >= limit:
            break
    return out


@lru_cache(maxsize=256)
def _robots(origin: str) -> RobotFileParser | None:
    parser = RobotFileParser()
    try:
        parser.parse(fetch(origin + "/robots.txt").text.splitlines())
    except CrawlError:
        return None
    return parser


def allowed_by_robots(url: str) -> bool:
    parsed = urlparse(url)
    parser = _robots(f"{parsed.scheme}://{parsed.netloc}")
    return parser is None or parser.can_fetch(get_settings().crawl_user_agent, url)
