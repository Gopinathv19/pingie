"""Live chat: handoff to a person, agent replies, and teaching the bot."""

from datetime import UTC, datetime, timedelta

from app.db.models import Conversation
from tests.conftest import sign_in
from tests.test_widget_api import ORIGIN, ask, live_bot, start  # noqa: F401

API = "/api/v1"
UNKNOWN = "Do you ship to Antarctica by penguin?"


def go_available(client):
    assert client.post(f"{API}/me/presence", json={"available": True}).status_code == 204


def test_no_agent_online_falls_back_to_email(client, live_bot):
    cid, headers = start(client, live_bot)
    reply = ask(client, live_bot, cid, headers, UNKNOWN).json()
    assert reply["outcome"] == "fallback" and reply["offer_human"] is False and reply["asks_for_email"] is True

    r = client.post(f"{API}/widget/{live_bot['id']}/conversations/{cid}/handoff", headers=headers)
    assert r.json()["status"] == "unavailable"


def test_handoff_takeover_and_reply(client, owner, live_bot):
    go_available(client)
    cid, headers = start(client, live_bot)
    reply = ask(client, live_bot, cid, headers, UNKNOWN).json()
    assert reply["offer_human"] is True and reply["asks_for_email"] is False

    assert client.post(f"{API}/widget/{live_bot['id']}/conversations/{cid}/handoff", headers=headers).json()["status"] == "waiting"
    live = client.get(f"{API}/me/live").json()
    assert [w["conversation_id"] for w in live["waiting"]] == [cid]

    # While waiting or human, the bot stays quiet.
    quiet = ask(client, live_bot, cid, headers, "hello? anyone there").json()
    assert quiet["outcome"] == "human" and quiet["message_id"] is None

    r = client.post(f"{API}/bots/{live_bot['id']}/conversations/{cid}/reply", json={"text": "Hi! Gopi here, let me check."})
    assert r.status_code == 201 and r.json()["role"] == "agent"

    upd = client.get(f"{API}/widget/{live_bot['id']}/conversations/{cid}/updates", headers=headers).json()
    assert upd["status"] == "human" and upd["agent"]["name"] == "Gopi"
    assert [m["role"] for m in upd["messages"]] == ["system", "system", "agent"]

    assert client.post(f"{API}/bots/{live_bot['id']}/conversations/{cid}/handback").status_code == 204
    assert ask(client, live_bot, cid, headers, "Can I export invoices as CSV?").json()["outcome"] == "answered"


def test_waiting_too_long_asks_for_email(db, client, live_bot):
    go_available(client)
    cid, headers = start(client, live_bot)
    ask(client, live_bot, cid, headers, UNKNOWN)
    client.post(f"{API}/widget/{live_bot['id']}/conversations/{cid}/handoff", headers=headers)
    conv = db.get(Conversation, cid)
    conv.handoff_requested_at = datetime.now(UTC) - timedelta(minutes=10)
    db.commit()

    upd = client.get(f"{API}/widget/{live_bot['id']}/conversations/{cid}/updates", headers=headers).json()
    assert upd["status"] == "bot" and upd["messages"][-1]["asks_for_email"] is True
    assert ask(client, live_bot, cid, headers, "me@visitor.com").json()["outcome"] == "lead"


def test_viewers_cannot_reply(db, client, owner, live_bot):
    r = client.post(f"{API}/bots/{live_bot['id']}/invitations", json={"email": "guest@other.com", "role": "viewer"})
    token = r.json()["invite_url"].rsplit("/", 1)[1]
    cid, _ = start(client, live_bot)
    sign_in(db, client, "guest@other.com", "Guest", "google-2")
    client.post(f"{API}/invitations/by-token/{token}/accept")
    assert client.post(f"{API}/bots/{live_bot['id']}/conversations/{cid}/reply", json={"text": "hi"}).status_code == 403


def test_teaching_an_answer_uses_one_source(client, live_bot):
    for q in ("Do you ship to Antarctica?", "Is there a student discount?"):
        r = client.post(f"{API}/bots/{live_bot['id']}/answers", json={"question": q, "answer": "Yes, we do."})
        assert r.status_code == 201, r.text
    names = [s["name"] for s in client.get(f"{API}/bots/{live_bot['id']}/sources").json()["items"]]
    assert names.count("Team answers") == 1
    assert len(client.get(f"{API}/bots/{live_bot['id']}/answers").json()) == 2


def test_team_answers_reach_memora_as_markdown(client, fakes, live_bot):
    memora, _ = fakes
    r = client.post(f"{API}/bots/{live_bot['id']}/answers", json={"question": "Do you clean bathrooms?", "answer": "Yes, every day."})
    assert r.status_code == 201, r.text
    pushed = [s for s in memora.sources.values() if s["filename"] == "Team answers.md"]
    assert len(pushed) == 1 and "Do you clean bathrooms?" in pushed[0]["text"]


def test_a_failed_push_saves_nothing(client, fakes, live_bot):
    memora, _ = fakes
    memora.fail_uploads = True
    r = client.post(f"{API}/bots/{live_bot['id']}/answers", json={"question": "Do you clean bathrooms?", "answer": "Yes."})
    assert r.status_code >= 400
    assert client.get(f"{API}/bots/{live_bot['id']}/answers").json() == []

    memora.fail_uploads = False
    assert client.post(f"{API}/bots/{live_bot['id']}/answers", json={"question": "Do you clean bathrooms?", "answer": "Yes."}).status_code == 201
    assert len(client.get(f"{API}/bots/{live_bot['id']}/answers").json()) == 1


def test_saving_the_same_answer_twice_keeps_one(client, live_bot):
    body = {"question": "Is there any human available?", "answer": "Customer: hi\nTeam member: hello", "kind": "conversation"}
    for _ in range(2):
        assert client.post(f"{API}/bots/{live_bot['id']}/answers", json=body).status_code == 201
    assert len(client.get(f"{API}/bots/{live_bot['id']}/answers").json()) == 1


def test_finished_team_chats_are_remembered_in_memora(db, client, fakes, live_bot):
    from app.services import memory_service

    memora, _ = fakes
    go_available(client)
    cid, headers = start(client, live_bot)
    ask(client, live_bot, cid, headers, "Do you clean bathrooms on weekends? mail me at a@b.com")
    client.post(f"{API}/widget/{live_bot['id']}/conversations/{cid}/handoff", headers=headers)
    client.post(f"{API}/bots/{live_bot['id']}/conversations/{cid}/reply", json={"text": "Yes, bathrooms on weekends cost 20% more."})

    # Still live: not finished yet.
    assert memory_service.archive_due(db, memora.client()) == 0

    client.post(f"{API}/bots/{live_bot['id']}/conversations/{cid}/close")
    db.expire_all()
    assert memory_service.archive_due(db, memora.client()) == 1
    conv = db.get(Conversation, cid)
    text = memora.sources[str(conv.memora_source_id)]["text"]
    assert "bathrooms on weekends cost 20% more" in text and "a@b.com" not in text
    assert memory_service.archive_due(db, memora.client()) == 0  # nothing new

    # Another visitor asks something similar: the past chat is evidence.
    cid2, headers2 = start(client, live_bot)
    reply = ask(client, live_bot, cid2, headers2, "weekends bathrooms").json()
    assert any(c["source_name"] == "Past conversations" for c in reply.get("citations", [])), reply

    # Clearing history removes the copies from Memora.
    assert client.delete(f"{API}/bots/{live_bot['id']}/conversations").status_code == 204
    assert str(conv.memora_source_id) not in memora.sources


def test_editing_an_answer_repushes_team_answers(client, fakes, live_bot):
    memora, _ = fakes
    a = client.post(f"{API}/bots/{live_bot['id']}/answers", json={"question": "Weekend cleaning?", "answer": "No."}).json()
    r = client.patch(f"{API}/bots/{live_bot['id']}/answers/{a['id']}", json={"question": "Weekend cleaning?", "answer": "Yes, 20% extra."})
    assert r.status_code == 200 and r.json()["answer"] == "Yes, 20% extra."
    pushed = [s["text"] for s in memora.sources.values() if s["filename"] == "Team answers.md"]
    assert len(pushed) == 1 and "20% extra" in pushed[0] and "No." not in pushed[0]
