"use client";

import { useState } from "react";
import { UpgradeModal } from "@/components/billing/UpgradeModal";
import { useSession } from "@/components/session/SessionProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import s from "./billing.module.css";

import { SUPPORT_EMAIL } from "@/components/billing/PlanCards";

export function BillingView() {
  const { org } = useSession();
  const [showUpgrade, setShowUpgrade] = useState(false);
  const usage = org.usage;
  const planLabel = org.plan_name;
  const canUpgrade = org.can_upgrade;

  return (
    <div className="page">
      {showUpgrade && <UpgradeModal trigger="your plan" onClose={() => setShowUpgrade(false)} />}
      <PageHeader
        title="Plan & Billing"
        description="Your current plan, usage, and upgrade options."
      />

      <div className={s.layout}>
        <Panel title="Current plan">
          <div className="panel-body">
            <div className={s.planRow}>
              <div>
                <div className={s.planName}>{planLabel}</div>
                {canUpgrade && (
                  <div className={s.planDesc}>
                    Upgrade to unlock more capacity and features.
                  </div>
                )}
              </div>
              {canUpgrade && (
                <button type="button" className="btn btn-primary" onClick={() => setShowUpgrade(true)}>
                  Upgrade plan
                </button>
              )}
              {!canUpgrade && (
                <a
                  href={`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent("Billing enquiry – Pingie")}`}
                  className="btn"
                >
                  Contact support
                </a>
              )}
            </div>
          </div>
        </Panel>

        <Panel title="Usage this month">
          <div className="panel-body">
            <div className={s.usageGrid}>
              <UsageStat label="Messages" used={usage.messages_used} limit={usage.messages_limit} />
              <UsageStat label="Bots" used={usage.bots_used} limit={usage.bots_limit} />
            </div>
          </div>
        </Panel>

        <Panel title="Plan limits">
          <div className="panel-body">
            <table className={s.limitsTable}>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Your limit</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Bots</td>
                  <td>{usage.bots_limit}</td>
                </tr>
                <tr>
                  <td>Messages / month</td>
                  <td>{usage.messages_limit.toLocaleString("en-US")}</td>
                </tr>
                <tr>
                  <td>Knowledge sources / bot</td>
                  <td>{usage.sources_limit === 9999 ? "Unlimited" : usage.sources_limit}</td>
                </tr>
                <tr>
                  <td>Team members</td>
                  <td>{usage.members_limit === 9999 ? "Unlimited" : usage.members_limit}</td>
                </tr>
                <tr>
                  <td>People per shared bot</td>
                  <td>{usage.shares_limit >= 9999 ? "Unlimited" : usage.shares_limit}</td>
                </tr>
                <tr>
                  <td>Remove Pingie branding</td>
                  <td>{usage.remove_branding ? "Yes" : "No (upgrade required)"}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Panel>

        {canUpgrade && (
          <Panel title="Want more?">
            <div className="panel-body">
              <p style={{ margin: "0 0 12px", fontSize: 14, color: "var(--text-2)", lineHeight: 1.5 }}>
                Email us at{" "}
                <a href={`mailto:${SUPPORT_EMAIL}`} style={{ color: "var(--accent)" }}>
                  {SUPPORT_EMAIL}
                </a>{" "}
                and we&apos;ll move you to a bigger plan within 24 hours.
              </p>
              <button type="button" className="btn btn-primary" onClick={() => setShowUpgrade(true)}>
                See upgrade options
              </button>
            </div>
          </Panel>
        )}
      </div>
    </div>
  );
}

function UsageStat({ label, used, limit }: { label: string; used: number; limit: number }) {
  const pct = Math.min(100, (used / Math.max(limit, 1)) * 100);
  const atLimit = used >= limit;
  return (
    <div className={s.usageStat}>
      <div className={s.usageStatHead}>
        <span>{label}</span>
        <span className="mono" style={{ color: atLimit ? "var(--danger-soft)" : undefined }}>
          {used.toLocaleString("en-US")} / {limit.toLocaleString("en-US")}
        </span>
      </div>
      <div className={s.track}>
        <div
          className={s.fill}
          style={{ width: `${pct}%`, background: atLimit ? "var(--danger-soft)" : undefined }}
        />
      </div>
    </div>
  );
}
