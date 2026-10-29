"use client";

import { useEffect } from "react";
import { Icon } from "@/components/Icon";
import { useSession } from "@/components/session/SessionProvider";
import { ContactEmail, PlanCards } from "./PlanCards";
import s from "./upgrade.module.css";

interface Props {
  trigger?: string;
  onClose: () => void;
}

export function UpgradeModal({ trigger, onClose }: Props) {
  const { org } = useSession();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className={s.overlay} role="dialog" aria-modal="true" aria-label="Upgrade plan" onClick={onClose}>
      <div className={s.modal} onClick={(e) => e.stopPropagation()}>
        <div className={s.header}>
          <div className={s.icon}>
            <Icon name="spark" size={22} />
          </div>
          <button type="button" className={s.close} aria-label="Close" onClick={onClose}>
            <Icon name="close" size={16} />
          </button>
        </div>

        <h2 className={s.title}>Choose your plan</h2>
        {trigger && (
          <p className={s.body}>
            You&apos;ve reached the limit for <strong>{trigger}</strong> on the {org.plan_name} plan.
          </p>
        )}

        <PlanCards currentPlan={org.plan} />
        <ContactEmail />
      </div>
    </div>
  );
}
