"use client";

import { useSession } from "@/components/session/SessionProvider";
import { InlineError } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { Invitation } from "@/lib/types";
import { useAction, useApi } from "@/lib/use-api";
import s from "./sharing.module.css";

/** Invites waiting for the signed-in user, with Accept / Decline. */
export function PendingInvites({ onAccepted }: { onAccepted: (inv: Invitation) => void }) {
  const { data, reload } = useApi(() => api.invitations.mine(), []);
  const { reloadOrg } = useSession();
  const action = useAction();
  if (!data?.length) return null;

  const respond = async (inv: Invitation, accept: boolean) => {
    const result = await action.run(() => (accept ? api.invitations.accept(inv.id) : api.invitations.decline(inv.id)));
    if (!result) return;
    reload();
    if (accept) {
      if (inv.kind === "workspace") reloadOrg();
      onAccepted(inv);
    }
  };

  return (
    <>
      {data.map((inv) => (
        <div key={inv.id} className={s.banner} role="status">
          <span>
            <strong>{inv.invited_by ?? "Someone"}</strong> invited you to{" "}
            {inv.kind === "bot" ? (
              <>
                the bot <strong>{inv.bot_name}</strong>
              </>
            ) : (
              <>
                the workspace <strong>{inv.organization_name}</strong>
              </>
            )}{" "}
            as {inv.role === "editor" ? "an editor" : "a viewer"}.
          </span>
          <button type="button" className="btn btn-sm" disabled={action.busy} onClick={() => respond(inv, false)}>
            Decline
          </button>
          <button type="button" className="btn btn-sm btn-primary" disabled={action.busy} onClick={() => respond(inv, true)}>
            Accept
          </button>
        </div>
      ))}
      <InlineError message={action.error} />
    </>
  );
}
