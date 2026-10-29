"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { InlineError, Loading } from "@/components/ui/States";
import { ApiError, api } from "@/lib/api";
import type { Invitation, User } from "@/lib/types";
import { useAction } from "@/lib/use-api";

type State = { invite: Invitation; user: User | null } | { error: string };

export function InviteView({ token }: { token: string }) {
  const [state, setState] = useState<State | null>(null);
  const [done, setDone] = useState<"accepted" | "declined" | null>(null);
  const action = useAction();
  const loginHref = `/login?next=${encodeURIComponent(`/invite/${token}`)}`;

  useEffect(() => {
    Promise.all([api.invitations.preview(token), api.auth.me().catch(() => null)]).then(
      ([invite, user]) => setState({ invite, user }),
      (e) => setState({ error: e instanceof ApiError ? e.message : "Could not load this invite" }),
    );
  }, [token]);

  const accept = async (invite: Invitation) => {
    const r = await action.run(() => api.invitations.acceptToken(token));
    if (!r) return;
    if (invite.kind === "workspace") {
      localStorage.setItem("pingie-org", invite.organization_id);
      window.location.href = "/bots";
    } else {
      window.location.href = invite.bot_id ? `/bots/${invite.bot_id}` : "/bots";
    }
  };

  const decline = async () => {
    if (await action.run(() => api.invitations.declineToken(token))) setDone("declined");
  };

  const switchAccount = async () => {
    await api.auth.logout().catch(() => undefined);
    window.location.href = loginHref;
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        backgroundImage: "radial-gradient(var(--dot) 1px, transparent 1px)",
        backgroundSize: "18px 18px",
      }}
    >
      <div className="panel" style={{ width: "100%", maxWidth: 440 }}>
        <div className="panel-body" style={{ display: "flex", flexDirection: "column", gap: 14, padding: 28 }}>
          <span className="mono subtle" style={{ fontSize: 12 }}>Pingie invitation</span>
          {!state && <Loading height={120} />}
          {state && "error" in state && (
            <>
              <h1 style={{ margin: 0, fontSize: 20 }}>This invite can&apos;t be used</h1>
              <p className="muted" style={{ margin: 0 }}>{state.error}</p>
              <Link href="/bots" className="btn" style={{ alignSelf: "flex-start" }}>Go to Pingie</Link>
            </>
          )}
          {state && "invite" in state && (
            <Body
              invite={state.invite}
              user={state.user}
              done={done}
              busy={action.busy}
              loginHref={loginHref}
              onAccept={() => accept(state.invite)}
              onDecline={decline}
              onSwitch={switchAccount}
            />
          )}
          <InlineError message={action.error} />
        </div>
      </div>
    </div>
  );
}

function Body({
  invite,
  user,
  done,
  busy,
  loginHref,
  onAccept,
  onDecline,
  onSwitch,
}: {
  invite: Invitation;
  user: User | null;
  done: "accepted" | "declined" | null;
  busy: boolean;
  loginHref: string;
  onAccept: () => void;
  onDecline: () => void;
  onSwitch: () => void;
}) {
  const target = invite.kind === "bot" ? `the bot “${invite.bot_name}”` : `the workspace “${invite.organization_name}”`;
  const roleText = invite.role === "editor" ? "an editor (can make changes)" : "a viewer (read-only)";

  return (
    <>
      <h1 style={{ margin: 0, fontSize: 20, lineHeight: 1.35 }}>
        {invite.invited_by ?? "Someone"} invited you to {target}
      </h1>
      <p className="muted" style={{ margin: 0, fontSize: 14 }}>
        You&apos;ll join as {roleText}. This invite was sent to <span className="mono">{invite.email}</span>.
      </p>

      {done === "declined" ? (
        <p style={{ margin: 0 }}>Invite declined. You can close this page.</p>
      ) : invite.status !== "pending" ? (
        <>
          <p style={{ margin: 0 }}>This invite is {invite.status}. Ask {invite.invited_by ?? "the owner"} for a new one.</p>
          <Link href="/bots" className="btn" style={{ alignSelf: "flex-start" }}>Go to Pingie</Link>
        </>
      ) : !user ? (
        <Link href={loginHref} className="btn btn-primary" style={{ alignSelf: "flex-start" }}>
          Sign in to accept
        </Link>
      ) : !invite.email_matches ? (
        <>
          <p style={{ margin: 0, fontSize: 14 }}>
            You&apos;re signed in as <strong>{user.email}</strong>, but this invite is for a different email.
          </p>
          <button type="button" className="btn" style={{ alignSelf: "flex-start" }} onClick={onSwitch}>
            Sign in with another account
          </button>
        </>
      ) : (
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={onAccept}>
            {busy ? "Joining…" : "Accept invite"}
          </button>
          <button type="button" className="btn" disabled={busy} onClick={onDecline}>
            Decline
          </button>
        </div>
      )}
    </>
  );
}
