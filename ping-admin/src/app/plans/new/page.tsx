import Link from "next/link";
import { redirect } from "next/navigation";
import { AdminApiError, adminApi } from "@/lib/api";
import { PlanForm, parsePlanForm } from "../PlanForm";

export const metadata = { title: "New plan" };

async function createAction(formData: FormData) {
  "use server";
  const key = String(formData.get("key") ?? "").trim().toLowerCase();
  let error: string | null = null;
  try {
    await adminApi.createPlan({ key, ...parsePlanForm(formData) });
  } catch (e) {
    error = e instanceof AdminApiError ? e.message : "Could not create the plan";
  }
  redirect(error ? `/plans/new?error=${encodeURIComponent(error)}` : "/plans?saved=1");
}

export default async function NewPlanPage({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const { error } = await searchParams;
  return (
    <div style={{ padding: "32px 40px", maxWidth: 760 }}>
      <Link href="/plans" style={{ fontSize: 13, color: "var(--text-3)" }}>← Back to plans</Link>
      <h1 style={{ fontSize: 20, fontWeight: 700, margin: "16px 0 24px" }}>New plan</h1>
      <PlanForm action={createAction} error={error} />
    </div>
  );
}
