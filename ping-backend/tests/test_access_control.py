"""Access-control boundaries: workspace isolation, roles, shares, invitations,
access removal, secrets, live chat lists, exports and sessions.

Needs TEST_DATABASE_URL (a throwaway PostgreSQL) like the other API tests.
"""

import csv
import io
import uuid
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings
from app.db.models import BotShare, Conversation, Invitation, Organization, Users
from app.services import organization_service, plan_service
from tests.conftest import sign_in
from tests.test_dashboard_api import HANDBOOK
from tests.test_sharing_api import as_user, share, token_of
from tests.test_widget_api import ask, live_bot, start  # noqa: F401  (live_bot is a fixture)

API = "/api/v1"


def _first_org(client) -> str:
    return client.get(f"{API}/orgs").json()[0]["id"]


def _to_pro(db, user) -> None:
    org, _ = organization_service.list_for_user(db, user)[0]
    plan_service.apply_plan(db, org, "pro")
    db.commit()


def _new_bot(client, org_id, name="Second bot", domain="second.example.com") -> dict:
    r = client.post(f"{API}/orgs/{org_id}/bots", json={"name": name, "domain": domain})
    assert r.status_code == 201, r.text
    return r.json()


def _workspace_member(db, client, owner, org_id, email, role, sub):
    """Invite `email` to the owner's workspace and accept as them; returns the user."""
    as_user(client, owner)
    r = client.post(f"{API}/orgs/{org_id}/invitations", json={"email": email, "role": role})
    assert r.status_code == 201, r.text
    user = sign_in(db, client, email, email.split("@")[0], sub)
    assert client.post(f"{API}/invitations/by-token/{token_of(r.json())}/accept").status_code == 200
    return user


def _accepted_share(db, client, owner, bot_id, email, role, sub):
    as_user(client, owner)
    token = share(client, bot_id, email, role)
    user = sign_in(db, client, email, email.split("@")[0], sub)
    assert client.post(f"{API}/invitations/by-token/{token}/accept").status_code == 200
    return user


def _a_workspace_with_data(db, client, owner, bot):
    """Owner A's bot with a chat, a source, an answer, a saved reply and a pending invite."""
    cid, _ = start(client, bot)
    sid = client.get(f"{API}/bots/{bot['id']}/sources").json()["items"][0]["id"]
    aid = client.post(f"{API}/bots/{bot['id']}/answers", json={"question": "Do you ship abroad?", "answer": "Yes, worldwide."}).json()["id"]
    rid = client.post(f"{API}/bots/{bot['id']}/saved-replies", json={"title": "Hi", "body": "Hello!"}).json()["id"]
    inv = client.post(f"{API}/bots/{bot['id']}/invitations", json={"email": "pending@other.com", "role": "viewer"}).json()["id"]
    return cid, sid, aid, rid, inv


# --- workspace isolation ----------------------------------------------------------------

def test_another_workspace_sees_none_of_a_bots_data(db, client, owner, org_id, live_bot):
    bot = live_bot
    cid, sid, aid, rid, inv = _a_workspace_with_data(db, client, owner, bot)

    sign_in(db, client, "boss@rival.com", "Rival", "google-rival")
    b = f"{API}/bots/{bot['id']}"
    for path in (
        "", "/overview", "/install", "/sources", "/answers", "/conversations", f"/conversations/{cid}",
        "/conversations/export.csv", "/leads", "/saved-replies", "/domains", "/shares", "/appearance",
        f"/conversations/{cid}/updates",
    ):
        assert client.get(b + path).status_code == 404, path
    for method, path, body in (
        ("patch", "", {"name": "Hijacked"}),
        ("delete", "", None),
        ("delete", f"/sources/{sid}", None),
        ("patch", f"/answers/{aid}", {"question": "Do you ship abroad?", "answer": "No."}),
        ("delete", f"/saved-replies/{rid}", None),
        ("post", f"/conversations/{cid}/takeover", None),
        ("post", f"/conversations/{cid}/reply", {"text": "hi"}),
        ("delete", "/conversations", None),
        ("delete", f"/invitations/{inv}", None),
        ("post", "/invitations", {"email": "x@rival.com", "role": "editor"}),
    ):
        r = getattr(client, method)(b + path, **({"json": body} if body is not None else {}))
        assert r.status_code == 404, (method, path, r.status_code)

    for path in (f"/orgs/{org_id}", f"/orgs/{org_id}/members", f"/orgs/{org_id}/bots"):
        assert client.get(API + path).status_code == 404, path
    assert client.post(f"{API}/orgs/{org_id}/bots", json={"name": "Planted", "domain": "x.example.com"}).status_code == 404
    assert client.delete(f"{API}/orgs/{org_id}/invitations/{inv}").status_code == 404


def test_ids_from_another_workspace_fail_under_your_own_bot(db, client, owner, live_bot):
    cid, sid, aid, rid, inv = _a_workspace_with_data(db, client, owner, live_bot)

    sign_in(db, client, "boss@rival.com", "Rival", "google-rival")
    mine = _new_bot(client, _first_org(client), "Rival bot", "rival.example.com")
    b = f"{API}/bots/{mine['id']}"
    assert client.get(f"{b}/conversations/{cid}").status_code == 404
    assert client.post(f"{b}/conversations/{cid}/reply", json={"text": "hi"}).status_code == 404
    assert client.post(f"{b}/conversations/{cid}/memory/approve").status_code == 404
    assert client.delete(f"{b}/sources/{sid}").status_code == 404
    assert client.patch(f"{b}/answers/{aid}", json={"question": "Q?", "answer": "A."}).status_code == 404
    assert client.patch(f"{b}/saved-replies/{rid}", json={"body": "x"}).status_code == 404
    assert client.delete(f"{b}/invitations/{inv}").status_code == 404
    # An answer can't be copied into a bot in someone else's workspace.
    r = client.post(f"{b}/answers", json={"question": "Q?", "answer": "A.", "target_bot_ids": [live_bot["id"]]})
    assert r.status_code in (403, 404)


def test_ids_from_another_bot_in_the_same_workspace_fail(db, client, owner, live_bot):
    cid, sid, aid, rid, _ = _a_workspace_with_data(db, client, owner, live_bot)
    _to_pro(db, owner)
    other = _new_bot(client, _first_org(client))
    b = f"{API}/bots/{other['id']}"
    assert client.get(f"{b}/conversations/{cid}").status_code == 404
    assert client.delete(f"{b}/sources/{sid}").status_code == 404
    assert client.delete(f"{b}/answers/{aid}").status_code == 404
    assert client.delete(f"{b}/saved-replies/{rid}").status_code == 404


# --- roles ---------------------------------------------------------------------------------

def test_a_viewer_share_cannot_change_anything(db, client, owner, live_bot):
    bot = live_bot
    cid, sid, _, rid, _ = _a_workspace_with_data(db, client, owner, bot)
    appearance = client.get(f"{API}/bots/{bot['id']}/appearance").json()
    _accepted_share(db, client, owner, bot["id"], "guest@other.com", "viewer", "google-2")

    b = f"{API}/bots/{bot['id']}"
    assert client.get(b).status_code == 200
    for method, path, kwargs in (
        ("patch", "", {"json": {"name": "x"}}),
        ("put", "/appearance", {"json": appearance}),
        ("post", "/domains", {"json": {"host": "evil.example.com"}}),
        ("post", "/sources/upload", {"files": {"file": ("x.pdf", HANDBOOK, "application/pdf")}}),
        ("post", "/sources/url", {"json": {"url": "https://help.acme.com/x", "kind": "url"}}),
        ("delete", f"/sources/{sid}", {}),
        ("post", "/answers", {"json": {"question": "Q?", "answer": "A."}}),
        ("post", "/saved-replies", {"json": {"title": "t", "body": "b"}}),
        ("delete", f"/saved-replies/{rid}", {}),
        ("post", f"/conversations/{cid}/takeover", {}),
        ("post", f"/conversations/{cid}/reply", {"json": {"text": "hi"}}),
        ("post", f"/conversations/{cid}/memory/approve", {}),
        ("post", "/memory/forget", {}),
        ("post", "/alerts/test", {}),
        ("delete", "/conversations", {}),
        ("post", "/invitations", {"json": {"email": "x@y.com", "role": "viewer"}}),
        ("delete", "", {}),
    ):
        r = getattr(client, method)(b + path, **kwargs)
        assert r.status_code == 403, (method, path, r.status_code)


def test_workspace_editors_and_viewers_cannot_manage_people(db, client, owner, org_id, bot):
    _to_pro(db, owner)
    viewer = _workspace_member(db, client, owner, org_id, "viewer@acme.com", "viewer", "google-v")
    editor = _workspace_member(db, client, owner, org_id, "editor@acme.com", "editor", "google-e")

    as_user(client, editor)
    assert client.post(f"{API}/orgs/{org_id}/invitations", json={"email": "x@acme.com", "role": "viewer"}).status_code == 403
    assert client.patch(f"{API}/orgs/{org_id}/members/{viewer.id}", json={"role": "editor"}).status_code == 403
    assert client.delete(f"{API}/orgs/{org_id}/members/{viewer.id}").status_code == 403
    assert client.post(f"{API}/bots/{bot['id']}/invitations", json={"email": "x@y.com", "role": "viewer"}).status_code == 403

    as_user(client, viewer)
    assert client.post(f"{API}/orgs/{org_id}/bots", json={"name": "Nope", "domain": "nope.example.com"}).status_code == 403
    assert client.patch(f"{API}/bots/{bot['id']}", json={"name": "x"}).status_code == 403

    as_user(client, owner)
    assert client.patch(f"{API}/orgs/{org_id}/members/{editor.id}", json={"role": "owner"}).status_code == 422
    assert client.patch(f"{API}/orgs/{org_id}/members/{owner.id}", json={"role": "viewer"}).status_code == 403
    assert client.delete(f"{API}/orgs/{org_id}/members/{owner.id}").status_code == 403
    assert client.delete(f"{API}/orgs/{org_id}/members/me").status_code == 403
    assert client.patch(f"{API}/bots/{bot['id']}/shares/{editor.id}", json={"role": "owner"}).status_code in (404, 422)


# --- invitations --------------------------------------------------------------------------

def test_expired_revoked_declined_and_replaced_invites_cannot_be_used(db, client, owner, bot):
    b = f"{API}/bots/{bot['id']}"
    expired = client.post(f"{b}/invitations", json={"email": "late@other.com", "role": "viewer"}).json()
    row = db.get(Invitation, uuid.UUID(expired["id"]))
    row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    revoked = client.post(f"{b}/invitations", json={"email": "revoked@other.com", "role": "viewer"}).json()
    assert client.delete(f"{b}/invitations/{revoked['id']}").status_code == 204
    declined = client.post(f"{b}/invitations", json={"email": "no@other.com", "role": "viewer"}).json()
    replaced = client.post(f"{b}/invitations", json={"email": "resent@other.com", "role": "viewer"}).json()
    assert client.post(f"{b}/invitations/{replaced['id']}/resend").status_code == 200

    sign_in(db, client, "late@other.com", "Late", "google-late")
    assert client.post(f"{API}/invitations/by-token/{token_of(expired)}/accept").status_code == 409
    sign_in(db, client, "revoked@other.com", "Revoked", "google-rev")
    assert client.post(f"{API}/invitations/by-token/{token_of(revoked)}/accept").status_code == 409
    sign_in(db, client, "no@other.com", "No", "google-no")
    assert client.post(f"{API}/invitations/by-token/{token_of(declined)}/decline").status_code == 200
    assert client.post(f"{API}/invitations/by-token/{token_of(declined)}/accept").status_code == 409
    sign_in(db, client, "resent@other.com", "Resent", "google-resent")
    assert client.post(f"{API}/invitations/by-token/{token_of(replaced)}/accept").status_code == 404

    # Someone else's invite can't be accepted by id either.
    assert client.post(f"{API}/invitations/{expired['id']}/accept").status_code == 404
    assert db.query(BotShare).count() == 0  # none of the four invites gave anyone access
    assert client.get(f"{API}/bots/{bot['id']}").status_code == 404


# --- removing access -------------------------------------------------------------------------

def test_removed_members_and_shares_lose_access_at_once(db, client, owner, org_id, bot):
    _to_pro(db, owner)
    mate = _workspace_member(db, client, owner, org_id, "mate@acme.com", "editor", "google-mate")
    guest = _accepted_share(db, client, owner, bot["id"], "guest@other.com", "editor", "google-guest")
    viewer = _accepted_share(db, client, owner, bot["id"], "down@other.com", "editor", "google-down")

    as_user(client, owner)
    assert client.delete(f"{API}/orgs/{org_id}/members/{mate.id}").status_code == 204
    assert client.delete(f"{API}/bots/{bot['id']}/shares/{guest.id}").status_code == 204
    assert client.patch(f"{API}/bots/{bot['id']}/shares/{viewer.id}", json={"role": "viewer"}).status_code == 204

    as_user(client, mate)
    assert client.get(f"{API}/bots/{bot['id']}").status_code == 404
    assert client.get(f"{API}/orgs/{org_id}").status_code == 404
    as_user(client, guest)
    assert client.get(f"{API}/bots/{bot['id']}").status_code == 404
    as_user(client, viewer)
    assert client.patch(f"{API}/bots/{bot['id']}", json={"name": "x"}).status_code == 403


def test_a_bot_share_does_not_survive_leaving_the_workspace(db, client, owner, org_id, bot):
    """Regression: a share from before someone joined gave them their old
    (editor) access back after they were removed from the workspace."""
    _to_pro(db, owner)
    user = _accepted_share(db, client, owner, bot["id"], "both@acme.com", "editor", "google-both")
    _workspace_member(db, client, owner, org_id, "both@acme.com", "viewer", "google-both")

    detail = client.get(f"{API}/bots/{bot['id']}").json()
    assert detail["access_role"] == "viewer" and detail["access_via"] == "workspace"
    assert db.query(BotShare).filter(BotShare.user_id == user.id).count() == 0

    as_user(client, owner)
    assert client.delete(f"{API}/orgs/{org_id}/members/{user.id}").status_code == 204
    as_user(client, user)
    assert client.get(f"{API}/bots/{bot['id']}").status_code == 404
    assert client.patch(f"{API}/bots/{bot['id']}", json={"name": "Back in"}).status_code == 404


def test_a_bot_invite_accepted_by_a_member_adds_no_share(db, client, owner, org_id, bot):
    _to_pro(db, owner)
    token = share(client, bot["id"], "late@acme.com", "editor")
    user = _workspace_member(db, client, owner, org_id, "late@acme.com", "viewer", "google-late")
    assert client.post(f"{API}/invitations/by-token/{token}/accept").status_code == 200
    assert db.query(BotShare).filter(BotShare.user_id == user.id).count() == 0

    as_user(client, owner)
    client.delete(f"{API}/orgs/{org_id}/members/{user.id}")
    as_user(client, user)
    assert client.get(f"{API}/bots/{bot['id']}").status_code == 404


# --- secrets, live lists, exports -------------------------------------------------------------

def test_viewers_do_not_receive_alert_webhook_urls(db, client, owner, bot):
    slack = "https://hooks.slack.com/services/T000/B000/secret"
    hook = "https://hooks.example.com/pingie"
    assert client.patch(f"{API}/bots/{bot['id']}", json={"alert_slack_url": slack, "alert_webhook_url": hook}).status_code == 200

    _accepted_share(db, client, owner, bot["id"], "viewer@other.com", "viewer", "google-view")
    seen = client.get(f"{API}/bots/{bot['id']}").json()
    assert seen["alert_slack_url"] == "" and seen["alert_webhook_url"] == ""
    assert seen["alerts_configured"] is True

    _accepted_share(db, client, owner, bot["id"], "editor@other.com", "editor", "google-edit")
    seen = client.get(f"{API}/bots/{bot['id']}").json()
    assert seen["alert_slack_url"] == slack and seen["alert_webhook_url"] == hook


def test_live_list_shows_only_chats_you_can_answer(db, client, owner, live_bot):
    cid, _ = start(client, live_bot)
    conv = db.get(Conversation, uuid.UUID(cid))
    conv.status, conv.handoff_requested_at = "waiting", datetime.now(UTC)
    db.commit()

    assert [w["conversation_id"] for w in client.get(f"{API}/me/live").json()["waiting"]] == [cid]
    _accepted_share(db, client, owner, live_bot["id"], "viewer@other.com", "viewer", "google-view")
    assert client.get(f"{API}/me/live").json()["waiting"] == []
    sign_in(db, client, "boss@rival.com", "Rival", "google-rival")
    assert client.get(f"{API}/me/live").json()["waiting"] == []


def test_export_neutralises_spreadsheet_formulas(client, live_bot):
    cid, headers = start(client, live_bot)
    ask(client, live_bot, cid, headers, '=HYPERLINK("https://evil.example","Click")')
    body = client.get(f"{API}/bots/{live_bot['id']}/conversations/export.csv").text
    rows = list(csv.DictReader(io.StringIO(body)))
    visitor_rows = [r for r in rows if r["role"] == "visitor"]
    assert visitor_rows and all(not r["message"].startswith(("=", "+", "-", "@")) for r in visitor_rows)
    assert any(r["message"].startswith("'=HYPERLINK") for r in visitor_rows)


# --- sessions and suspended workspaces -----------------------------------------------------------

def test_disabled_users_and_forged_tokens_are_rejected(db, client, owner):
    assert client.get(f"{API}/auth/me").status_code == 200
    settings = get_settings()
    now = datetime.now(UTC)
    forged = jwt.encode(
        {"sub": str(owner.id), "email": owner.email, "iss": settings.auth_jwt_issuer, "typ": "session",
         "iat": now, "exp": now + timedelta(hours=1)},
        "not-the-real-secret-but-long-enough-0000",
        algorithm="HS256",
    )
    client.cookies.set(settings.auth_cookie_name, forged)
    assert client.get(f"{API}/auth/me").status_code == 401

    as_user(client, owner)
    tampered = client.cookies.get(settings.auth_cookie_name)[:-2] + "xx"
    client.cookies.set(settings.auth_cookie_name, tampered)
    assert client.get(f"{API}/auth/me").status_code == 401

    db.get(Users, owner.id).status = "disabled"
    db.commit()
    as_user(client, owner)
    assert client.get(f"{API}/auth/me").status_code == 401


def test_a_suspended_workspace_is_out_of_reach(db, client, owner, org_id, bot):
    db.get(Organization, uuid.UUID(org_id)).status = "suspended"
    db.commit()
    assert client.get(f"{API}/bots/{bot['id']}").status_code == 404
    assert client.get(f"{API}/orgs/{org_id}").status_code == 404
    assert client.get(f"{API}/orgs/{org_id}/bots").status_code == 404
