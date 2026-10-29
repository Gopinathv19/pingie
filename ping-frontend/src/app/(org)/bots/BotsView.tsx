"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "@/components/Icon";
import { UpgradeModal } from "@/components/billing/UpgradeModal";
import { useSession } from "@/components/session/SessionProvider";
import { PendingInvites } from "@/components/sharing/PendingInvites";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, Loading } from "@/components/ui/States";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { botHref } from "@/lib/nav";
import type { BotSummary, SharedBot } from "@/lib/types";
import { useAction, useApi } from "@/lib/use-api";
import s from "./bots.module.css";

export function BotsView() {
  const { org, canEdit } = useSession();
  const { data: bots, error, reload } = useApi(() => api.orgs.bots(org.id), [org.id]);
  const shared = useApi(() => api.shares.sharedWithMe(), []);
  const [showUpgrade, setShowUpgrade] = useState(false);
  const usage = org.usage;
  const botsUsed = bots?.length ?? usage.bots_used;
  const atBotLimit = botsUsed >= usage.bots_limit;

  return (
    <div className="page">
      {showUpgrade && <UpgradeModal trigger="bots" onClose={() => setShowUpgrade(false)} />}
      <PageHeader
        title="Bots"
        description={`Support bots for ${org.name}. Each one answers from its own sources on its own domains.`}
        actions={
          !canEdit ? null : atBotLimit ? (
            <button type="button" className="btn btn-primary" onClick={() => setShowUpgrade(true)}>
              <Icon name="spark" size={14} strokeWidth={2.2} />
              Upgrade to add more
            </button>
          ) : (
            <Link href="/bots/new" className="btn btn-primary">
              <Icon name="plus" size={14} strokeWidth={2.2} />
              New bot
            </Link>
          )
        }
      />

      <PendingInvites onAccepted={() => shared.reload()} />

      <div className={s.usage}>
        <Meter label="Messages this month" used={usage.messages_used} limit={usage.messages_limit} />
        <Meter label="Bots" used={botsUsed} limit={usage.bots_limit} />
        <span className="badge">{org.plan_name} plan</span>
        {org.role !== "owner" && <span className="badge">{org.role}</span>}
      </div>

      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!bots && !error && <Loading />}
      {bots && bots.length === 0 && (
        <div className="panel">
          <div className="empty" style={{ padding: "56px 18px" }}>
            {canEdit ? (
              <>
                <h2 style={{ margin: "0 0 6px", fontSize: 16, color: "var(--text)" }}>Create your first bot</h2>
                <p style={{ margin: "0 0 16px" }}>Point it at your docs or website and embed it in minutes.</p>
                <Link href="/bots/new" className="btn btn-primary">
                  <Icon name="plus" size={14} strokeWidth={2.2} />
                  New bot
                </Link>
              </>
            ) : (
              <p style={{ margin: 0 }}>No bots in this workspace yet.</p>
            )}
          </div>
        </div>
      )}
      {bots && bots.length > 0 && (
        <div className={s.grid}>
          {bots.map((b) => (
            <BotCard key={b.id} bot={b} />
          ))}
          {!canEdit ? null : atBotLimit ? (
            <button type="button" className={s.newCard} onClick={() => setShowUpgrade(true)}>
              <Icon name="spark" size={20} />
              Upgrade to add more bots
            </button>
          ) : (
            <Link href="/bots/new" className={s.newCard}>
              <Icon name="plus" size={20} />
              Create a bot
            </Link>
          )}
        </div>
      )}

      {shared.data && shared.data.length > 0 && (
        <section className={s.sharedSection} aria-labelledby="shared-heading">
          <h2 id="shared-heading" className={s.sectionTitle}>
            Shared with me <span className="subtle">({shared.data.length})</span>
          </h2>
          <div className={s.grid}>
            {shared.data.map((b) => (
              <SharedCard key={b.id} bot={b} onRemoved={shared.reload} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function BotCard({ bot: b, footer }: { bot: BotSummary; footer?: React.ReactNode }) {
  return (
    <Link href={botHref(b.id)} className={s.card}>
      <div className={s.cardHead}>
        <span aria-hidden="true" className={s.mark} style={{ background: b.color }}>
          {b.initials}
        </span>
        <span className={s.title}>
          <strong>{b.name}</strong>
          <span className={s.domain}>{b.domain}</span>
        </span>
        <StatusBadge status={b.status} />
      </div>
      <div className={s.stats}>
        <span className={s.stat}>
          <span className={s.statValue}>{b.conversations_30d.toLocaleString("en-US")}</span>
          <span className={s.statLabel}>Chats · 30d</span>
        </span>
        <span className={s.stat}>
          <span className={s.statValue}>{b.conversations_30d ? `${b.resolution_rate}%` : "—"}</span>
          <span className={s.statLabel}>Resolved</span>
        </span>
        <span className={s.stat}>
          <span className={s.statValue}>{b.sources}</span>
          <span className={s.statLabel}>Sources</span>
        </span>
      </div>
      <div className={s.cardFoot}>
        {footer ?? (
          <>
            <span className="mono">{b.id}</span>
            <span>Updated {relativeTime(b.updated_at)}</span>
          </>
        )}
      </div>
    </Link>
  );
}

function SharedCard({ bot, onRemoved }: { bot: SharedBot; onRemoved: () => void }) {
  const remove = useAction();
  return (
    <BotCard
      bot={bot}
      footer={
        <>
          <span>
            {bot.shared_by ? `Shared by ${bot.shared_by}` : bot.organization_name} ·{" "}
            <span className="badge">{bot.role}</span>
          </span>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={remove.busy}
            onClick={(e) => {
              e.preventDefault();
              if (confirm(`Remove "${bot.name}" from your list? You'll need a new invite to get it back.`)) {
                remove.run(() => api.shares.leave(bot.id)).then(onRemoved);
              }
            }}
          >
            Remove
          </button>
        </>
      }
    />
  );
}

function Meter({ label, used, limit }: { label: string; used: number; limit: number }) {
  return (
    <div className={s.usageMeter}>
      <div className={s.usageHead}>
        <span style={{ fontWeight: 600 }}>{label}</span>
        <span className="mono">
          {used.toLocaleString("en-US")} / {limit.toLocaleString("en-US")}
        </span>
      </div>
      <div className={s.track}>
        <div className={s.fill} style={{ width: `${Math.min(100, (used / Math.max(limit, 1)) * 100)}%` }} />
      </div>
    </div>
  );
}
