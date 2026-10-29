import Link from "next/link";
import { redirect } from "next/navigation";
import { AdminApiError, adminApi } from "@/lib/api";
import { PlanForm, parsePlanForm } from "../PlanForm";

export const metadata = { title: "Edit plan" };

async function updateAction(key: string, formData: FormData) {
  "use server";
  let error: string | null = null;
  try {
    await adminApi.updatePlan(key, {
      ...parsePlanForm(formData),
      apply_to_existing: formData.get("apply_to_existing") === "on",
    });
  } catch (e) {
    error = e instanceof AdminApiError ? e.message : "Could not save the plan";
  }
  const path = `/plans/${encodeURIComponent(key)}`;
  redirect(error ? `${path}?error=${encodeURIComponent(error)}` : "/plans?saved=1");
}

export default async function EditPlanPage({
  params,
  searchParams,
}: {
  params: Promise<{ key: string }>;
  searchParams: Promise<{ error?: string }>;
}) {
  const { key } = await params;
  const { error } = await searchParams;
  const plan = await adminApi.getPlan(decodeURIComponent(key));

  return (
    <div style={{ padding: "32px 40px", maxWidth: 760 }}>
      <Link href="/plans" style={{ fontSize: 13, color: "var(--text-3)" }}>← Back to plans</Link>
      <h1 style={{ fontSize: 20, fontWeight: 700, margin: "16px 0 4px" }}>{plan.name}</h1>
      <p className="muted" style={{ fontSize: 13, marginBottom: 24 }}>
        {plan.org_count} organization{plan.org_count === 1 ? "" : "s"} on this plan
      </p>
      <PlanForm plan={plan} action={updateAction.bind(null, plan.key)} error={error} />
    </div>
  );
}
