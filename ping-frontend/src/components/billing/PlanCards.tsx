"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { api } from "@/lib/api";
import type { Plan } from "@/lib/types";
import s from "./upgrade.module.css";

export const SUPPORT_EMAIL = "support@pingie.app";

let cache: Promise<Plan[]> | null = null;

export function usePlans() {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    cache ??= api.plans.list();
    cache.then(setPlans, () => {
      cache = null;
      setError(true);
    });
  }, []);
  return { plans, error };
}

function price(plan: Plan) {
  if (plan.price_monthly === null) return <>{plan.price_label || "Custom"}</>;
  return (
    <>
      {plan.price_label || `$${plan.price_monthly}`}
      <span>/month</span>
    </>
  );
}

export function PlanCards({ currentPlan }: { currentPlan: string }) {
  const { plans, error } = usePlans();

  if (error) return <p className={s.body}>Could not load plans. Email us at {SUPPORT_EMAIL}.</p>;
  if (!plans) return <p className={s.body}>Loading plans…</p>;

  return (
    <div className={s.plans} style={{ "--cols": Math.min(plans.length, 4) } as React.CSSProperties}>
      {plans.map((plan) => {
        const current = plan.key.toUpperCase() === currentPlan.toUpperCase();
        return (
          <div key={plan.key} className={`${s.plan} ${plan.highlighted ? s.planPro : ""} ${current ? s.planCurrent : ""}`}>
            {current ? (
              <div className={`${s.planBadge} ${s.badgeCurrent}`}>Current</div>
            ) : (
              plan.highlighted && <div className={s.planBadge}>Popular</div>
            )}
            <div className={s.planName}>{plan.name}</div>
            <div className={s.planPrice}>{price(plan)}</div>
            {plan.description && <p className={s.planDesc}>{plan.description}</p>}
            <ul className={s.planFeatures}>
              {plan.features.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

export function ContactEmail() {
  const [copied, setCopied] = useState(false);
  const copy = () =>
    navigator.clipboard.writeText(SUPPORT_EMAIL).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });

  return (
    <div className={s.contact}>
      <p className={s.contactLabel}>To upgrade, email us and we&apos;ll set you up within 24 hours:</p>
      <div className={s.emailRow}>
        <span className={s.emailAddress}>{SUPPORT_EMAIL}</span>
        <button type="button" className={`btn btn-sm ${s.copyBtn}`} onClick={copy}>
          <Icon name={copied ? "check" : "copy"} size={13} />
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}
