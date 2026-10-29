"use client";

import Link from "next/link";
import { useState } from "react";
import { UpgradeModal } from "@/components/billing/UpgradeModal";
import { useBot } from "@/components/session/BotProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Loading } from "@/components/ui/States";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { PeopleManager } from "./PeopleManager";

export function SharingView() {
  const { bot } = useBot();
  const isOwner = bot.access_role === "owner";
  const { data, error, reload } = useApi(
    () => (isOwner ? api.shares.list(bot.id) : Promise.resolve(null)),
    [bot.id, isOwner],
  );
  const [showUpgrade, setShowUpgrade] = useState(false);

  return (
    <div className="page">
      {showUpgrade && <UpgradeModal trigger="people per shared bot" onClose={() => setShowUpgrade(false)} />}
      <PageHeader
        title="Sharing"
        description={
          <>
            Give someone outside your workspace access to just this bot. It shows up in their &ldquo;Shared with
            me&rdquo; list. To give access to every bot, invite them on the{" "}
            <Link href="/settings/members">Members</Link> page.
          </>
        }
      />
      {!isOwner && <div className="notice">Only the bot&apos;s owner can manage sharing.</div>}
      {error && <ErrorState message={error.message} onRetry={reload} />}
      {isOwner && !data && !error && <Loading />}
      {data && (
        <PeopleManager
          data={data}
          canManage
          reload={reload}
          seatsLabel="People with access"
          onLimit={() => setShowUpgrade(true)}
          actions={{
            invite: (email, role) => api.shares.invite(bot.id, email, role),
            resend: (id) => api.shares.resend(bot.id, id),
            revoke: (id) => api.shares.revoke(bot.id, id),
            setRole: (uid, role) => api.shares.setRole(bot.id, uid, role),
            remove: (uid) => api.shares.remove(bot.id, uid),
          }}
        />
      )}
    </div>
  );
}
