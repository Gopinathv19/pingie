import pytest

from app.core.errors import ValidationError
from app.ingestion import crawler
from app.ingestion.html import html_to_markdown
from app.services.domain_service import host_matches, normalize_host

PAGE = """<html><head><title>Billing · Acme Help</title></head><body>
<nav>Home Pricing</nav><div class="cookie-banner">We use cookies</div>
<main><h1>Exporting invoices</h1><p>Go to <b>Settings</b> → Billing, then <a href="#">Invoices</a>.</p>
<ol><li>Open Invoices</li><li>Click Export</li></ol>
<table><tr><th>Plan</th><th>Price</th></tr><tr><td>Pro</td><td>$29</td></tr></table></main>
<footer>© Acme</footer><script>track()</script></body></html>"""


def test_html_to_markdown_keeps_structure_and_drops_chrome():
    page = html_to_markdown(PAGE)
    md = page.markdown
    assert page.title == "Billing · Acme Help"
    assert "# Exporting invoices" in md
    assert "Go to Settings → Billing, then Invoices." in md
    assert "1. Open Invoices" in md and "2. Click Export" in md
    assert "| Pro | $29 |" in md
    for junk in ("Home Pricing", "cookies", "© Acme", "track()"):
        assert junk not in md


@pytest.mark.parametrize("url", ["http://127.0.0.1/x", "http://169.254.169.254/latest", "http://localhost:8000", "http://10.0.0.5"])
def test_private_hosts_are_refused(url):
    with pytest.raises(crawler.CrawlError):
        crawler._check_host(url)


def test_normalize_url():
    assert crawler.normalize_url("help.acme.com/docs#top") == "https://help.acme.com/docs"
    with pytest.raises(ValidationError):
        crawler.normalize_url("ftp://x")


def test_sitemap_index_is_followed(monkeypatch):
    import httpx

    docs = {
        "https://a.com/sitemap.xml": b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://a.com/s1.xml</loc></sitemap></sitemapindex>',
        "https://a.com/s1.xml": b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://a.com/a</loc></url><url><loc>https://a.com/b</loc></url><url><loc>https://a.com/a</loc></url></urlset>',
    }
    monkeypatch.setattr(crawler, "fetch", lambda url: httpx.Response(200, content=docs[url]))
    assert crawler.sitemap_urls("https://a.com/sitemap.xml", 10) == ["https://a.com/a", "https://a.com/b"]


def test_xml_bombs_are_rejected(monkeypatch):
    import httpx

    bomb = b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><urlset>&b;</urlset>'
    monkeypatch.setattr(crawler, "fetch", lambda url: httpx.Response(200, content=bomb))
    with pytest.raises(Exception):
        crawler.sitemap_urls("https://a.com/sitemap.xml", 10)


def test_domain_matching():
    assert normalize_host("https://Help.Acme.com/path") == "help.acme.com"
    assert host_matches("*.acme.com", "help.acme.com")
    assert host_matches("*.acme.com", "acme.com")
    assert not host_matches("*.acme.com", "evilacme.com")
    assert not host_matches("acme.com", "help.acme.com")
    with pytest.raises(ValidationError):
        normalize_host("not a host")
