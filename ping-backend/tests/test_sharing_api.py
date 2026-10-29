"""Sharing: bot shares, workspace members, invitations and role checks."""

from app.core.config import get_settings
from app.core.security import create_session_token
from app.services import organization_service, plan_service
from tests.conftest import sign_in

API = "/api/v1"


def as_user(client, user):
    client.cookies.set(get_settings().auth_cookie_name, create_session_token(user.id, user.email))


def token_of(invite: dict) -> str:
    return invite["invite_url"].rsplit("/", 1)[1]


def share(client, bot_id, email, role):
    r = client.post(f"{API}/bots/{bot_id}/invitations", json={"email": email, "role": role})
    assert r.status_code == 201, r.text
    return token_of(r.json())


def test_viewer_share_is_read_only(db, client, owner, bot):
    token = share(client, bot["id"], "guest@other.com", "viewer")
    guest = sign_in(db, client, "guest@other.com", "Guest", "google-2")

    assert client.get(f"{API}/bots/{bot['id']}").status_code == 404
    preview = client.get(f"{API}/invitations/by-token/{token}").json()
    assert preview["email_matches"] is True and preview["bot_name"] == "Acme Help Center"
    assert client.post(f"{API}/invitations/by-token/{token}/accept").status_code == 200

    detail = client.get(f"{API}/bots/{bot['id']}").json()
    assert detail["access_role"] == "viewer" and detail["access_via"] == "share"
    assert client.patch(f"{API}/bots/{bot['id']}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{API}/bots/{bot['id']}").status_code == 403
    shared = client.get(f"{API}/shared-bots").json()
    assert [b["id"] for b in shared] == [bot["id"]] and shared[0]["role"] == "viewer"

    as_user(client, owner)
    assert client.patch(f"{API}/bots/{bot['id']}/shares/{guest.id}", json={"role": "editor"}).status_code == 204
    as_user(client, guest)
    assert client.patch(f"{API}/bots/{bot['id']}", json={"name": "Renamed"}).status_code == 200
    assert client.delete(f"{API}/bots/{bot['id']}").status_code == 403


def test_invite_needs_the_invited_email_and_works_once(db, client, owner, bot):
    token = share(client, bot["id"], "guest@other.com", "viewer")
    sign_in(db, client, "intruder@evil.com", "Eve", "google-3")
    assert client.post(f"{API}/invitations/by-token/{token}/accept").status_code == 403
    assert client.get(f"{API}/bots/{bot['id']}").status_code == 404

    sign_in(db, client, "guest@other.com", "Guest", "google-2")
    assert client.post(f"{API}/invitations/by-token/{token}/accept").status_code == 200
    assert client.post(f"{API}/invitations/by-token/{token}/accept").status_code == 409


def test_free_plan_limits_shares_per_bot(db, client, owner, bot):
    for i in range(3):
        share(client, bot["id"], f"p{i}@other.com", "viewer")
    r = client.post(f"{API}/bots/{bot['id']}/invitations", json={"email": "p3@other.com", "role": "viewer"})
    assert r.status_code == 402


def test_workspace_invites_need_seats(db, client, owner, org_id, bot):
    r = client.post(f"{API}/orgs/{org_id}/invitations", json={"email": "mate@acme.com", "role": "editor"})
    assert r.status_code == 402

    org, _ = organization_service.list_for_user(db, owner)[0]
    plan_service.apply_plan(db, org, "pro")
    db.commit()
    r = client.post(f"{API}/orgs/{org_id}/invitations", json={"email": "mate@acme.com", "role": "editor"})
    assert r.status_code == 201, r.text
    invite_id = r.json()["id"]

    mate = sign_in(db, client, "mate@acme.com", "Mate", "google-4")
    mine = client.get(f"{API}/invitations/mine").json()
    assert [i["id"] for i in mine] == [invite_id]
    assert client.post(f"{API}/invitations/{invite_id}/accept").status_code == 200

    orgs = {o["id"]: o["role"] for o in client.get(f"{API}/orgs").json()}
    assert orgs[org_id] == "editor"
    assert client.patch(f"{API}/bots/{bot['id']}", json={"name": "Team edit"}).status_code == 200
    assert client.delete(f"{API}/bots/{bot['id']}/conversations").status_code == 403
    assert client.patch(f"{API}/orgs/{org_id}", json={"name": "Mine now"}).status_code == 403

    assert client.delete(f"{API}/orgs/{org_id}/members/me").status_code == 204
    assert client.get(f"{API}/bots/{bot['id']}").status_code == 404
    assert mate.id not in {m["user_id"] for m in client.get(f"{API}/orgs/{org_id}/members").json().get("members", [])}


def test_non_owners_cannot_share(db, client, owner, bot):
    token = share(client, bot["id"], "guest@other.com", "editor")
    sign_in(db, client, "guest@other.com", "Guest", "google-2")
    client.post(f"{API}/invitations/by-token/{token}/accept")
    r = client.post(f"{API}/bots/{bot['id']}/invitations", json={"email": "x@y.com", "role": "viewer"})
    assert r.status_code == 403
