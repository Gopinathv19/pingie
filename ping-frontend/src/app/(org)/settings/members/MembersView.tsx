"use client";

import { useState } from "react";
import { UpgradeModal } from "@/components/billing/UpgradeModal";
import { useSession } from "@/components/session/SessionProvider";
import { PeopleManager } from "@/components/sharing/PeopleManager";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, InlineError, Loading } from "@/components/ui/States";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/use-api";

export function MembersView() {
  const { org, isOwner } = useSession();
  const { data, error, reload } = useApi(() => api.members.list(org.id), [org.id]);
  const [showUpgrade, setShowUpgrade] = useState(false);
  const leave = useAction();

  return (
    <div className="page">
      {showUpgrade && <UpgradeModal trigger="workspace members" onClose={() => setShowUpgrade(false)} />}
      <PageHeader
        title="Members"
        description={
          isOwner
            ? `Invite people to ${org.name}. Members see and work on every bot in this workspace.`
            : `People in ${org.name}. Only the owner can invite or remove members.`
        }
        actions={
          !isOwner && (
            <button
              type="button"
              className="btn btn-danger"
              disabled={leave.busy}
              onClick={() => {
                if (confirm(`Leave ${org.name}? You'll lose access to its bots.`)) {
                  leave.run(() => api.members.leave(org.id)).then(() => {
                    localStorage.removeItem("pingie-org");
                    window.location.href = "/bots";
                  });
                }
              }}
            >
              Leave workspace
            </button>
          )
        }
      />
      <InlineError message={leave.error} />
      {isOwner && org.usage.members_limit <= 1 && (
        <div className="notice" style={{ marginBottom: 16 }}>
          Your {org.plan_name} plan includes 1 seat (you). Upgrade to invite teammates, or share a single bot from its{" "}
          <strong>Sharing</strong> page instead.{" "}
          <button type="button" className="btn btn-sm btn-primary" onClick={() => setShowUpgrade(true)}>
            See plans
          </button>
        </div>
      )}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!data && !error && <Loading />}
      {data && (
        <PeopleManager
          data={data}
          canManage={isOwner}
          reload={reload}
          seatsLabel="Seats"
          onLimit={() => setShowUpgrade(true)}
          actions={{
            invite: (email, role) => api.members.invite(org.id, email, role),
            resend: (id) => api.members.resend(org.id, id),
            revoke: (id) => api.members.revoke(org.id, id),
            setRole: (uid, role) => api.members.setRole(org.id, uid, role),
            remove: (uid) => api.members.remove(org.id, uid),
          }}
        />
      )}
    </div>
  );
}
