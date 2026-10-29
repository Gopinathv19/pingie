"""Dashboard API: auth, organizations, bots, knowledge, domains, settings."""

from tests.conftest import sign_in

HANDBOOK = (
    "Billing exports\n\n"
    "Invoices can be exported from Settings, Billing, Invoices. Choose CSV or PDF and click Export.\n\n"
    "Exports older than 24 months are emailed to the account owner."
).encode()


def test_unauthenticated_requests_are_rejected(client):
    r = client.get("/api/v1/orgs")
    assert r.status_code == 401
    assert r.json()["code"] == "unauthenticated"


def test_first_sign_in_creates_an_organization(client, owner):
    me = client.get("/api/v1/auth/me").json()
    assert me["email"] == "owner@acme.com"
    orgs = client.get("/api/v1/orgs").json()
    assert len(orgs) == 1
    assert orgs[0]["name"] == "Gopi's workspace"
    assert orgs[0]["plan"] == "FREE"
    assert orgs[0]["role"] == "owner"
    usage = orgs[0]["usage"]
    assert (usage["messages_used"], usage["messages_limit"], usage["bots_used"], usage["bots_limit"]) == (0, 100, 0, 3)


def test_signing_in_twice_does_not_duplicate(db, client, owner):
    sign_in(db, client)
    assert len(client.get("/api/v1/orgs").json()) == 1


def test_create_and_configure_a_bot(client, org_id, bot):
    assert bot["id"].startswith("bot_") and len(bot["id"]) == 11
    assert bot["status"] == "draft"
    assert bot["domain"] == "help.acme.com"
    assert bot["initials"] == "AH"
    assert bot["counts"] == {"conversations": 0, "sources": 0, "domains": 1}
    assert bot["appearance"]["title"] == "Acme Help Center"

    r = client.patch(f"/api/v1/bots/{bot['id']}", json={"status": "live", "tone": "concise", "min_similarity": 0.4})
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["tone"], r.json()["min_similarity"]) == ("live", "concise", 0.4)
    assert client.patch(f"/api/v1/bots/{bot['id']}", json={"tone": "rude"}).status_code == 422

    cards = client.get(f"/api/v1/orgs/{org_id}/bots").json()
    assert [c["id"] for c in cards] == [bot["id"]]


def test_bot_limit_is_enforced(client, org_id, bot):
    for name in ("Two", "Three"):
        assert client.post(f"/api/v1/orgs/{org_id}/bots", json={"name": name + " bot", "domain": "a.com"}).status_code == 201
    r = client.post(f"/api/v1/orgs/{org_id}/bots", json={"name": "Four bot", "domain": "a.com"})
    assert r.status_code == 402
    assert r.json()["code"] == "quota_exceeded"


def test_other_users_cannot_see_a_bot(db, client, bot):
    sign_in(db, client, email="intruder@evil.com", sub="google-2", name="Eve")
    assert client.get(f"/api/v1/bots/{bot['id']}").status_code == 404
    assert client.get(f"/api/v1/bots/{bot['id']}/sources").status_code == 404


def test_appearance_validation(client, bot):
    url = f"/api/v1/bots/{bot['id']}/appearance"
    body = client.get(url).json() | {"accent": "#2563eb", "suggestions": ["  A?  ", "", "B?"]}
    saved = client.put(url, json=body).json()
    assert saved["accent"] == "#2563EB"
    assert saved["suggestions"] == ["A?", "B?"]
    assert client.put(url, json=body | {"accent": "blue"}).status_code == 422


def test_domains(client, bot):
    url = f"/api/v1/bots/{bot['id']}/domains"
    assert client.post(url, json={"host": "https://Shop.Acme.com/x"}).json()["host"] == "shop.acme.com"
    assert client.post(url, json={"host": "shop.acme.com"}).status_code == 409
    assert client.post(url, json={"host": "not a host"}).status_code == 422
    rows = client.get(url).json()
    assert {d["host"] for d in rows} == {"help.acme.com", "shop.acme.com"}
    shop = next(d for d in rows if d["host"] == "shop.acme.com")
    assert client.delete(f"{url}/{shop['id']}").status_code == 204
    assert len(client.get(url).json()) == 1


def test_upload_indexes_through_memora(client, bot, fakes):
    memora, _ = fakes
    r = client.post(
        f"/api/v1/bots/{bot['id']}/sources/upload",
        files={"file": ("acme-handbook.pdf", HANDBOOK, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "indexing"
    # The bot's Memora subject was created on first use, keyed by its public id.
    assert list(memora.subjects.values()) == [bot["id"]]

    listing = client.get(f"/api/v1/bots/{bot['id']}/sources").json()  # 1st check: still embedding
    assert listing["items"][0]["status"] == "indexing"

    import time
    time.sleep(5.1)  # past the refresh interval
    listing = client.get(f"/api/v1/bots/{bot['id']}/sources").json()
    item = listing["items"][0]
    assert (item["status"], item["chunks"], item["type"]) == ("ready", 3, "pdf")
    assert listing["summary"]["ready"] == 1


def test_upload_rejects_unsupported_files(client, bot):
    r = client.post(f"/api/v1/bots/{bot['id']}/sources/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 422


def test_add_page_crawls_cleans_and_pushes_markdown(client, bot, fakes, monkeypatch):
    from app.ingestion import crawler
    from app.ingestion.html import Page

    memora, _ = fakes
    page = Page(title="Security", markdown="# Security\n\n" + "We encrypt data at rest and in transit. " * 10)
    monkeypatch.setattr(crawler, "fetch_page", lambda url: crawler.FetchedPage(url=url, page=page))

    r = client.post(f"/api/v1/bots/{bot['id']}/sources/url", json={"url": "acme.com/security", "kind": "url"})
    assert r.status_code == 201
    assert r.json()["name"] == "acme.com/security"
    # TestClient runs background tasks before returning.
    item = client.get(f"/api/v1/bots/{bot['id']}/sources").json()["items"][0]
    assert item["status"] == "indexing"
    pushed = list(memora.sources.values())[0]
    assert pushed["text"].startswith("# Security")


def test_sitemap_creates_one_row_with_pages(client, bot, fakes, monkeypatch):
    from app.ingestion import crawler
    from app.ingestion.html import Page

    urls = ["https://help.acme.com/a", "https://help.acme.com/b", "https://help.acme.com/broken"]
    monkeypatch.setattr(crawler, "sitemap_urls", lambda url, limit: urls)
    monkeypatch.setattr(crawler, "allowed_by_robots", lambda url: True)

    def fetch_page(url):
        if url.endswith("broken"):
            raise crawler.CrawlError("No readable content was found on this page.")
        return crawler.FetchedPage(url=url, page=Page(title=url, markdown="words " * 50))

    monkeypatch.setattr(crawler, "fetch_page", fetch_page)
    client.post(f"/api/v1/bots/{bot['id']}/sources/url", json={"url": "https://help.acme.com", "kind": "sitemap"})
    items = client.get(f"/api/v1/bots/{bot['id']}/sources").json()["items"]
    assert len(items) == 1  # pages are not listed separately
    assert items[0]["url"] == "https://help.acme.com/sitemap.xml"
    assert items[0]["page_count"] == 3
    assert len(fakes[0].sources) == 2


def test_delete_source_removes_it_from_memora(client, bot, fakes):
    r = client.post(f"/api/v1/bots/{bot['id']}/sources/upload", files={"file": ("a.txt", HANDBOOK, "text/plain")})
    client.delete(f"/api/v1/bots/{bot['id']}/sources/{r.json()['id']}")
    assert fakes[0].sources == {}
    assert client.get(f"/api/v1/bots/{bot['id']}/sources").json()["items"] == []


def test_test_retrieval(client, bot):
    client.post(f"/api/v1/bots/{bot['id']}/sources/upload", files={"file": ("acme-handbook.pdf", HANDBOOK, "application/pdf")})
    r = client.post(f"/api/v1/bots/{bot['id']}/test", json={"query": "Can I export invoices?", "top_k": 3, "threshold": 0.5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["outcome"] == "answered"
    assert body["answer"] == "Yes. Go to Settings → Billing → Invoices and click Export."
    assert body["citations"][0]["source_name"] == "acme-handbook.pdf"
    assert body["chunks"][0]["above_threshold"] is True
    assert body["chunks_in_context"] >= 1


def test_install_info(client, bot):
    info = client.get(f"/api/v1/bots/{bot['id']}/install").json()
    assert f'data-bot-id="{bot["id"]}"' in info["snippet_html"]
    assert info["detected"] is False


def test_delete_bot_deletes_memora_subject(client, bot, fakes):
    client.post(f"/api/v1/bots/{bot['id']}/sources/upload", files={"file": ("a.txt", HANDBOOK, "text/plain")})
    assert client.delete(f"/api/v1/bots/{bot['id']}").status_code == 204
    assert fakes[0].subjects == {}
    assert client.get(f"/api/v1/bots/{bot['id']}").status_code == 404
