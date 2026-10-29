"""The public widget API and the analytics it feeds."""

import json

import pytest

from tests.test_dashboard_api import HANDBOOK

ORIGIN = {"Origin": "https://help.acme.com"}


@pytest.fixture()
def live_bot(client, bot):
    client.post(f"/api/v1/bots/{bot['id']}/sources/upload", files={"file": ("acme-handbook.pdf", HANDBOOK, "application/pdf")})
    client.patch(f"/api/v1/bots/{bot['id']}", json={"status": "live", "handoff_email": "support@acme.com"})
    return bot


def start(client, bot, visitor="visitor-12345678"):
    r = client.post(
        f"/api/v1/widget/{bot['id']}/conversations",
        json={"visitor_id": visitor, "page_url": "https://help.acme.com/billing?x=1"},
        headers=ORIGIN,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["conversation_id"], {**ORIGIN, "X-Conversation-Token": body["token"]}


def ask(client, bot, cid, headers, text, stream=False):
    return client.post(
        f"/api/v1/widget/{bot['id']}/conversations/{cid}/messages", json={"text": text, "stream": stream}, headers=headers
    )


def test_config_requires_an_allowed_origin(client, live_bot):
    url = f"/api/v1/widget/{live_bot['id']}/config"
    ok = client.get(url, headers=ORIGIN)
    assert ok.status_code == 200
    assert ok.json()["online"] is True
    assert ok.headers["access-control-allow-origin"] == "https://help.acme.com"
    assert client.get(url, headers={"Origin": "https://evil.com"}).status_code == 403
    assert client.get(url).status_code == 403
    # The load counts as an install.
    assert client.get(f"/api/v1/bots/{live_bot['id']}/install").json()["detected_host"] == "help.acme.com"


def test_preflight_is_answered_for_any_origin(client, live_bot):
    r = client.options(
        f"/api/v1/widget/{live_bot['id']}/conversations",
        headers={"Origin": "https://help.acme.com", "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 204
    assert "x-conversation-token" in r.headers["access-control-allow-headers"]


def test_draft_bots_only_load_on_localhost(client, bot):
    url = f"/api/v1/widget/{bot['id']}/config"
    assert client.get(url, headers=ORIGIN).status_code == 403
    assert client.get(url, headers={"Origin": "http://localhost:5173"}).json()["online"] is True


def test_answer_with_citation(client, live_bot, fakes):
    cid, headers = start(client, live_bot)
    r = ask(client, live_bot, cid, headers, "How do I export invoices?")
    assert r.status_code == 200, r.text
    reply = r.json()
    assert reply["outcome"] == "answered"
    assert reply["text"] == "Yes. Go to Settings → Billing → Invoices and click Export."
    assert reply["citations"][0]["source_name"] == "acme-handbook.pdf"
    assert reply["citations"][0]["location"] == "p. 4 · Billing"
    # Memora only retrieved (via /query/stream); Vizhi wrote the answer, and
    # the answer Memora streams after its evidence was never used.
    assert fakes[0].queries
    assert "Memora answer" not in reply["text"]


def test_small_talk_skips_retrieval(client, live_bot, fakes):
    cid, headers = start(client, live_bot)
    reply = ask(client, live_bot, cid, headers, "hi").json()
    assert reply["outcome"] == "smalltalk"
    assert fakes[0].queries == [] and fakes[1].calls == []


def test_fallback_then_lead_capture(client, live_bot):
    cid, headers = start(client, live_bot)
    reply = ask(client, live_bot, cid, headers, "Do you support SSO with Okta?").json()
    assert reply["outcome"] == "fallback"
    assert reply["asks_for_email"] is True

    thanks = ask(client, live_bot, cid, headers, "sure, it's maria@northwind.io").json()
    assert thanks["outcome"] == "lead"
    assert "maria@northwind.io" in thanks["text"]

    leads = client.get(f"/api/v1/bots/{live_bot['id']}/leads").json()
    assert [(l["email"], l["question"]) for l in leads] == [("maria@northwind.io", "Do you support SSO with Okta?")]
    convs = client.get(f"/api/v1/bots/{live_bot['id']}/conversations", params={"filter": "handoff"}).json()["items"]
    assert convs[0]["handoff_email"] == "maria@northwind.io"
    assert convs[0]["outcome"] == "fallback"


def test_streaming_reply(client, live_bot):
    cid, headers = start(client, live_bot)
    r = ask(client, live_bot, cid, headers, "How do I export invoices?", stream=True)
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [
        (block.split("\n")[0][7:], json.loads(block.split("\n")[1][6:]))
        for block in r.text.strip().split("\n\n")
    ]
    text = "".join(data["text"] for kind, data in events if kind == "delta")
    assert text == "Yes. Go to Settings → Billing → Invoices and click Export."
    kind, done = events[-1]
    assert kind == "done" and done["outcome"] == "answered" and done["citations"]


def test_streaming_fallback_shows_the_fallback_message(client, live_bot):
    cid, headers = start(client, live_bot)
    r = ask(client, live_bot, cid, headers, "Do you support SSO with Okta?", stream=True)
    assert "couldn't find that" in r.text
    assert '"outcome": "fallback"' in r.text


def test_conversation_token_is_required_and_scoped(client, live_bot):
    cid, headers = start(client, live_bot)
    other_cid, other_headers = start(client, live_bot, visitor="someone-else-999")
    assert ask(client, live_bot, cid, ORIGIN, "hi").status_code == 403
    assert ask(client, live_bot, cid, other_headers, "hi").status_code == 404


def test_memora_outage_degrades_to_an_apology(client, live_bot, fakes):
    fakes[0].fail_queries = True
    cid, headers = start(client, live_bot)
    reply = ask(client, live_bot, cid, headers, "How do I export invoices?").json()
    assert reply["outcome"] == "fallback"
    assert "trouble" in reply["text"]


def test_feedback_and_inbox(client, live_bot):
    cid, headers = start(client, live_bot)
    reply = ask(client, live_bot, cid, headers, "How do I export invoices?").json()
    r = client.post(
        f"/api/v1/widget/{live_bot['id']}/conversations/{cid}/messages/{reply['message_id']}/feedback",
        json={"value": "down"}, headers=headers,
    )
    assert r.status_code == 204

    base = f"/api/v1/bots/{live_bot['id']}/conversations"
    page = client.get(base).json()
    assert page["items"][0]["visitor"] == "Visitor #1"
    assert page["items"][0]["page"] == "/billing"
    assert page["items"][0]["preview"] == "How do I export invoices?"
    assert page["items"][0]["unread"] is True
    assert len(client.get(base, params={"filter": "down"}).json()["items"]) == 1
    assert client.get(base, params={"filter": "unanswered"}).json()["items"] == []
    assert len(client.get(base, params={"q": "export"}).json()["items"]) == 1

    detail = client.get(f"{base}/{cid}").json()
    assert [m["role"] for m in detail["messages"]] == ["visitor", "bot"]
    assert detail["messages"][1]["feedback"] == "down"
    assert client.get(base).json()["items"][0]["unread"] is False

    csv = client.get(f"{base}/export.csv")
    assert csv.headers["content-type"].startswith("text/csv")
    assert "How do I export invoices?" in csv.text


def test_overview_reflects_traffic(client, live_bot):
    cid, headers = start(client, live_bot)
    ask(client, live_bot, cid, headers, "How do I export invoices?")
    ask(client, live_bot, cid, headers, "Do you support SSO with Okta?")
    ask(client, live_bot, cid, headers, "maria@northwind.io")

    o = client.get(f"/api/v1/bots/{live_bot['id']}/overview", params={"range": "7d"}).json()
    kpis = {k["key"]: k for k in o["kpis"]}
    assert kpis["conversations"]["value"] == "1"
    assert kpis["messages"]["value"] == "6"
    assert kpis["resolution"]["value"] == "50%"
    assert kpis["handoffs"]["value"] == "1"
    assert kpis["visitors"]["value"] == "1"
    assert len(o["series"]) >= 7 and sum(p["conversations"] for p in o["series"]) == 1
    assert {x["key"]: x["pct"] for x in o["outcomes"]} == {"answered": 50, "partial": 0, "fallback": 50}
    assert o["knowledge_gaps"] == ["Do you support SSO with Okta?"]
    assert o["top_pages"] == [{"path": "/billing", "value": 1}]
    assert o["messages_per_day"][-1] == 6
    assert {q["text"] for q in o["top_questions"]} == {"How do I export invoices?", "Do you support SSO with Okta?"}
    exported = next(q for q in o["top_questions"] if q["text"].startswith("How"))
    assert exported["source"] == "acme-handbook.pdf" and exported["rate"] == "100%"
    for r in ("24h", "30d", "90d"):
        assert client.get(f"/api/v1/bots/{live_bot['id']}/overview", params={"range": r}).status_code == 200


def test_monthly_quota(client, db, live_bot):
    from sqlalchemy import update

    from app.db.models import Organization

    db.execute(update(Organization).values(messages_limit=2))
    db.commit()
    cid, headers = start(client, live_bot)
    assert ask(client, live_bot, cid, headers, "hi").status_code == 200   # 2 messages
    r = ask(client, live_bot, cid, headers, "hello")
    assert r.status_code == 402


def test_paused_bot_replies_with_offline_message(client, live_bot, fakes):
    client.patch(f"/api/v1/bots/{live_bot['id']}", json={"status": "paused", "offline_message": "Back at 9am."})
    cid, headers = start(client, live_bot)
    reply = ask(client, live_bot, cid, headers, "How do I export invoices?").json()
    assert reply["text"] == "Back at 9am." and reply["outcome"] == "offline"
    assert fakes[1].calls == []
