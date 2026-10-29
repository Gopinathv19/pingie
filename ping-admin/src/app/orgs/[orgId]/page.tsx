import Link from "next/link";
import { redirect } from "next/navigation";
import { AdminApiError, adminApi } from "@/lib/api";
import s from "./org.module.css";

export const metadata = { title: "Edit organization" };

async function updatePlanAction(orgId: string, formData: FormData) {
  "use server";
  const plan = String(formData.get("plan"));
  const custom = formData.get("custom") === "on";
  const num = (name: string) => {
    const v = formData.get(name);
    return v === null || v === "" ? undefined : Number(v);
  };
  const payload = custom
    ? {
        plan,
        messages_limit: num("messages_limit"),
        bots_limit: num("bots_limit"),
        sources_limit: num("sources_limit"),
        members_limit: num("members_limit"),
        shares_limit: num("shares_limit"),
        remove_branding: formData.get("remove_branding") === "on",
      }
    : { plan };

  let error: string | null = null;
  try {
    await adminApi.updateOrgPlan(orgId, payload);
  } catch (e) {
    error = e instanceof AdminApiError ? e.message : "Could not update the plan";
  }
  redirect(error ? `/orgs/${orgId}?error=${encodeURIComponent(error)}` : `/orgs/${orgId}?saved=1`);
}

export default async function OrgDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ orgId: string }>;
  searchParams: Promise<{ saved?: string; error?: string }>;
}) {
  const { orgId } = await params;
  const { saved, error } = await searchParams;
  const [org, plans] = await Promise.all([adminApi.getOrg(orgId), adminApi.listPlans()]);
  const choices = plans.filter((p) => p.active || p.key === org.plan);
  const action = updatePlanAction.bind(null, orgId);

  return (
    <div style={{ padding: "32px 40px", maxWidth: 720 }}>
      <div style={{ marginBottom: 20 }}>
        <Link href="/orgs" style={{ fontSize: 13, color: "var(--text-3)" }}>
          ← Back to organizations
        </Link>
      </div>

      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>{org.name}</h1>
      <div className="muted" style={{ fontSize: 13, marginBottom: 28 }}>
        {org.owner_email ?? "No owner"} · slug: {org.slug}
      </div>

      {saved && <div className="notice">Plan updated.</div>}
      {error && <div className="notice notice-error">{error}</div>}

      <div style={{ border: "1px solid var(--border)", background: "var(--surface)", padding: "16px 20px", marginBottom: 20 }}>
        <div style={{ fontWeight: 700, marginBottom: 12 }}>Current usage</div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
          <Stat label="Plan" value={org.plan_name} />
          <Stat label="Messages this month" value={`${org.messages_used.toLocaleString("en-US")} / ${org.messages_limit.toLocaleString("en-US")}`} />
          <Stat label="Bots" value={`${org.bots_used} / ${org.bots_limit}`} />
          <Stat label="Status" value={org.status} />
        </div>
      </div>

      <div style={{ border: "1px solid var(--border)", background: "var(--surface)", padding: "20px" }}>
        <div style={{ fontWeight: 700, marginBottom: 16 }}>Change plan</div>
        <form action={action} className={s.form}>
          <div className={s.field}>
            <label htmlFor="plan">Plan</label>
            <select id="plan" name="plan" defaultValue={org.plan}>
              {choices.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.name} — {p.price_label || "custom"} · {p.messages_limit.toLocaleString("en-US")} msgs, {p.bots_limit} bots
                  {p.active ? "" : " (archived)"}
                </option>
              ))}
            </select>
            <span className="muted" style={{ fontSize: 12, textTransform: "none", letterSpacing: 0, fontWeight: 400 }}>
              Limits come from the plan. Manage plans on the <Link href="/plans">Plans</Link> page.
            </span>
          </div>

          <div className={s.checkRow}>
            <input type="checkbox" id="custom" name="custom" />
            <label htmlFor="custom">Use custom limits for this organization (values below)</label>
          </div>

          <div className={s.grid}>
            <div className={s.field}>
              <label htmlFor="messages_limit">Messages limit / month</label>
              <input type="number" id="messages_limit" name="messages_limit" defaultValue={org.messages_limit} min={0} />
            </div>
            <div className={s.field}>
              <label htmlFor="bots_limit">Bots limit</label>
              <input type="number" id="bots_limit" name="bots_limit" defaultValue={org.bots_limit} min={0} />
            </div>
            <div className={s.field}>
              <label htmlFor="sources_limit">Sources per bot</label>
              <input type="number" id="sources_limit" name="sources_limit" defaultValue={org.sources_limit} min={0} />
            </div>
            <div className={s.field}>
              <label htmlFor="members_limit">Team members</label>
              <input type="number" id="members_limit" name="members_limit" defaultValue={org.members_limit} min={1} />
            </div>
            <div className={s.field}>
              <label htmlFor="shares_limit">People per shared bot</label>
              <input type="number" id="shares_limit" name="shares_limit" defaultValue={org.shares_limit} min={0} />
            </div>
          </div>

          <div className={s.checkRow}>
            <input type="checkbox" id="remove_branding" name="remove_branding" defaultChecked={org.remove_branding} />
            <label htmlFor="remove_branding">Allow removing &ldquo;Powered by Pingie&rdquo; branding</label>
          </div>

          <div style={{ display: "flex", gap: 10, marginTop: 8 }}>
            <button type="submit" className="btn btn-primary">Save changes</button>
            <Link href="/orgs" className="btn">Cancel</Link>
          </div>
        </form>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="muted" style={{ fontSize: 11, marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: 15 }}>{value}</div>
    </div>
  );
}
