"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import { Panel } from "@/components/ui/Panel";
import { InlineError } from "@/components/ui/States";
import { relativeTime } from "@/lib/format";
import type { Invitation, InviteRole, PeopleList } from "@/lib/types";
import { useAction } from "@/lib/use-api";
import s from "./sharing.module.css";

export interface PeopleActions {
  invite: (email: string, role: InviteRole) => Promise<Invitation>;
  resend: (invId: string) => Promise<Invitation>;
  revoke: (invId: string) => Promise<void>;
  setRole: (userId: string, role: InviteRole) => Promise<void>;
  remove: (userId: string) => Promise<void>;
}

const ROLE_HELP: Record<InviteRole, string> = {
  editor: "Can change settings, knowledge and appearance",
  viewer: "Read-only: overview, conversations, sources",
};

const unlimited = (n: number) => n >= 9999;

/** Invite form, people with access, and pending invites. Shared by workspace
 * members and bot sharing. */
export function PeopleManager({
  data,
  canManage,
  actions,
  reload,
  seatsLabel,
  onLimit,
}: {
  data: PeopleList;
  canManage: boolean;
  actions: PeopleActions;
  reload: () => void;
  seatsLabel: string;
  onLimit?: () => void;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<InviteRole>("viewer");
  const [link, setLink] = useState<{ email: string; url: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const action = useAction();
  const full = !unlimited(data.seats_limit) && data.seats_used >= data.seats_limit;

  const done = (inv: Invitation | undefined) => {
    if (inv?.invite_url) {
      setLink({ email: inv.email, url: inv.invite_url });
      setCopied(false);
    }
    reload();
  };

  const invite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (full && onLimit) return onLimit();
    const inv = await action.run(() => actions.invite(email.trim(), role));
    if (inv) {
      setEmail("");
      done(inv);
    }
  };

  const copy = (url: string) =>
    navigator.clipboard.writeText(url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });

  return (
    <div className={s.stack}>
      {canManage && (
        <Panel title="Invite someone">
          <form className="panel-body" onSubmit={invite}>
            <div className={s.inviteRow}>
              <input
                className="input"
                type="email"
                required
                placeholder="teammate@company.com"
                aria-label="Email address"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
              <select className="select" aria-label="Role" value={role} onChange={(e) => setRole(e.target.value as InviteRole)}>
                <option value="editor">Editor</option>
                <option value="viewer">Viewer</option>
              </select>
              <button type="submit" className="btn btn-primary" disabled={action.busy}>
                {full ? (
                  <>
                    <Icon name="spark" size={13} /> Upgrade
                  </>
                ) : action.busy ? (
                  "Sending…"
                ) : (
                  "Send invite"
                )}
              </button>
            </div>
            <span className="field-help">
              {ROLE_HELP[role]}. {seatsLabel}: {data.seats_used} /{" "}
              {unlimited(data.seats_limit) ? "unlimited" : data.seats_limit}
            </span>
            <InlineError message={action.error} />
            {link && (
              <div className={s.linkBox}>
                <span>
                  Invite sent to <strong>{link.email}</strong>. If email isn&apos;t set up, send them this link:
                </span>
                <div className={s.linkRow}>
                  <code className="mono">{link.url}</code>
                  <button type="button" className="btn btn-sm" onClick={() => copy(link.url)}>
                    <Icon name={copied ? "check" : "copy"} size={13} />
                    {copied ? "Copied" : "Copy"}
                  </button>
                </div>
              </div>
            )}
          </form>
        </Panel>
      )}

      <Panel title={`People with access (${data.people.length})`}>
        <ul className={s.list}>
          {data.people.map((p) => (
            <li key={p.user_id} className={s.row}>
              <span
                className={s.avatar}
                aria-hidden="true"
                style={p.avatar_url ? { backgroundImage: `url(${p.avatar_url})` } : undefined}
              >
                {p.avatar_url ? "" : (p.name || p.email)[0]?.toUpperCase()}
              </span>
              <span className={s.who}>
                <strong>{p.name || p.email}</strong>
                <span className="subtle">{p.email}</span>
              </span>
              {p.role === "owner" || !canManage ? (
                <span className="badge">{p.role}</span>
              ) : (
                <>
                  <select
                    className="select"
                    aria-label={`Role for ${p.email}`}
                    value={p.role}
                    disabled={action.busy}
                    onChange={(e) => action.run(() => actions.setRole(p.user_id, e.target.value as InviteRole)).then(reload)}
                  >
                    <option value="editor">Editor</option>
                    <option value="viewer">Viewer</option>
                  </select>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    aria-label={`Remove ${p.email}`}
                    disabled={action.busy}
                    onClick={() => {
                      if (confirm(`Remove ${p.email}? They lose access immediately.`)) {
                        action.run(() => actions.remove(p.user_id)).then(reload);
                      }
                    }}
                  >
                    <Icon name="trash" size={14} />
                  </button>
                </>
              )}
            </li>
          ))}
        </ul>
      </Panel>

      {data.invitations.length > 0 && (
        <Panel title={`Pending invites (${data.invitations.length})`}>
          <ul className={s.list}>
            {data.invitations.map((inv) => (
              <li key={inv.id} className={s.row}>
                <span className={s.avatar} aria-hidden="true">
                  <Icon name="mail" size={14} />
                </span>
                <span className={s.who}>
                  <strong>{inv.email}</strong>
                  <span className="subtle">
                    {inv.role} · invited {relativeTime(inv.created_at)}
                    {inv.invited_by ? ` by ${inv.invited_by}` : ""}
                  </span>
                </span>
                {canManage && (
                  <>
                    <button
                      type="button"
                      className="btn btn-sm"
                      disabled={action.busy}
                      onClick={() => action.run(() => actions.resend(inv.id)).then(done)}
                    >
                      New link
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={action.busy}
                      onClick={() => action.run(() => actions.revoke(inv.id)).then(reload)}
                    >
                      Revoke
                    </button>
                  </>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </div>
  );
}
