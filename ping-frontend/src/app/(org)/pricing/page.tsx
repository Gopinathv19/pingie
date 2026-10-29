"use client";

import { ContactEmail, PlanCards } from "@/components/billing/PlanCards";
import { useSession } from "@/components/session/SessionProvider";
import { PageHeader } from "@/components/ui/PageHeader";

export default function PricingPage() {
  const { org } = useSession();

  return (
    <div className="page">
      <PageHeader
        title="Plans & Pricing"
        description="Choose a plan that fits your team. Email us to upgrade and we'll set you up within 24 hours."
      />
      <PlanCards currentPlan={org.plan} />
      <ContactEmail />
    </div>
  );
}
