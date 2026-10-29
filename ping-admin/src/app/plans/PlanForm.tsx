import Link from "next/link";
import { MODEL_TIERS, type AdminPlan, type PlanValues } from "@/lib/api";
import s from "./plans.module.css";

export function parsePlanForm(formData: FormData): PlanValues {
  const str = (k: string) => String(formData.get(k) ?? "").trim();
  const int = (k: string) => Number(str(k) || 0);
  const on = (k: string) => formData.get(k) === "on";
  const price = str("price_monthly");
  return {
    name: str("name"),
    description: str("description"),
    price_monthly: price === "" ? null : Number(price),
    price_label: str("price_label"),
    messages_limit: int("messages_limit"),
    bots_limit: int("bots_limit"),
    sources_limit: int("sources_limit"),
    members_limit: int("members_limit"),
    shares_limit: int("shares_limit"),
    remove_branding: on("remove_branding"),
    model_tiers: MODEL_TIERS.filter((t) => on(`tier_${t}`)),
    features: str("features").split("\n").map((f) => f.trim()).filter(Boolean),
    is_public: on("is_public"),
    is_default: on("is_default"),
    highlighted: on("highlighted"),
    sort_order: int("sort_order"),
    active: on("active"),
  };
}

const BLANK: Omit<AdminPlan, "id" | "created_at" | "updated_at"> = {
  key: "",
  name: "",
  description: "",
  price_monthly: null,
  price_label: "",
  messages_limit: 1000,
  bots_limit: 3,
  sources_limit: 10,
  members_limit: 1,
  shares_limit: 3,
  remove_branding: false,
  model_tiers: ["fast"],
  features: [],
  is_public: true,
  is_default: false,
  highlighted: false,
  sort_order: 10,
  active: true,
  org_count: 0,
};

export function PlanForm({
  plan,
  action,
  error,
}: {
  plan?: AdminPlan;
  action: (formData: FormData) => Promise<void>;
  error?: string;
}) {
  const p = plan ?? BLANK;
  const editing = Boolean(plan);

  return (
    <form action={action} className={s.form}>
      {error && <div className="notice notice-error">{error}</div>}

      <section className={s.section}>
        <h2>Basics</h2>
        <div className={s.grid}>
          <label className={s.field}>
            <span>Key (used internally, cannot change)</span>
            <input name="key" defaultValue={p.key} required disabled={editing} pattern="[a-z0-9_\-]+" placeholder="startup" />
          </label>
          <label className={s.field}>
            <span>Display name</span>
            <input name="name" defaultValue={p.name} required placeholder="Startup" />
          </label>
          <label className={s.field}>
            <span>Monthly price (USD, empty = custom)</span>
            <input name="price_monthly" type="number" min={0} defaultValue={p.price_monthly ?? ""} />
          </label>
          <label className={s.field}>
            <span>Price label shown to customers</span>
            <input name="price_label" defaultValue={p.price_label} placeholder="$19 or Custom" />
          </label>
        </div>
        <label className={s.field}>
          <span>Description</span>
          <input name="description" defaultValue={p.description} placeholder="For small teams getting started" />
        </label>
      </section>

      <section className={s.section}>
        <h2>Limits</h2>
        <div className={s.grid}>
          <label className={s.field}>
            <span>Messages / month</span>
            <input name="messages_limit" type="number" min={0} required defaultValue={p.messages_limit} />
          </label>
          <label className={s.field}>
            <span>Bots</span>
            <input name="bots_limit" type="number" min={0} required defaultValue={p.bots_limit} />
          </label>
          <label className={s.field}>
            <span>Sources per bot</span>
            <input name="sources_limit" type="number" min={0} required defaultValue={p.sources_limit} />
          </label>
          <label className={s.field}>
            <span>Team members</span>
            <input name="members_limit" type="number" min={0} required defaultValue={p.members_limit} />
          </label>
          <label className={s.field}>
            <span>People per shared bot</span>
            <input name="shares_limit" type="number" min={0} required defaultValue={p.shares_limit} />
          </label>
        </div>
        <p className="muted" style={{ fontSize: 12 }}>Use 9999 for unlimited.</p>
        <div className={s.checks}>
          <span className={s.label}>Model tiers</span>
          {MODEL_TIERS.map((t) => (
            <label key={t} className={s.check}>
              <input type="checkbox" name={`tier_${t}`} defaultChecked={p.model_tiers.includes(t)} /> {t}
            </label>
          ))}
        </div>
        <label className={s.check}>
          <input type="checkbox" name="remove_branding" defaultChecked={p.remove_branding} /> Can remove &ldquo;Powered by Pingie&rdquo; badge
        </label>
      </section>

      <section className={s.section}>
        <h2>Pricing page</h2>
        <label className={s.field}>
          <span>Feature bullets (one per line)</span>
          <textarea name="features" rows={6} defaultValue={p.features.join("\n")} />
        </label>
        <label className={s.field} style={{ maxWidth: 200 }}>
          <span>Sort order (low → high)</span>
          <input name="sort_order" type="number" defaultValue={p.sort_order} />
        </label>
        <div className={s.checks}>
          <label className={s.check}><input type="checkbox" name="is_public" defaultChecked={p.is_public} /> Show to customers</label>
          <label className={s.check}><input type="checkbox" name="highlighted" defaultChecked={p.highlighted} /> &ldquo;Popular&rdquo; badge</label>
          <label className={s.check}><input type="checkbox" name="is_default" defaultChecked={p.is_default} /> Default for new signups</label>
          <label className={s.check}><input type="checkbox" name="active" defaultChecked={p.active} /> Active (uncheck to archive)</label>
        </div>
      </section>

      {editing && p.org_count > 0 && (
        <section className={s.section}>
          <label className={s.check}>
            <input type="checkbox" name="apply_to_existing" /> Apply the new limits to the {p.org_count} organization
            {p.org_count === 1 ? "" : "s"} on this plan (overwrites their custom limits)
          </label>
        </section>
      )}

      <div style={{ display: "flex", gap: 10 }}>
        <button type="submit" className="btn btn-primary">{editing ? "Save plan" : "Create plan"}</button>
        <Link href="/plans" className="btn">Cancel</Link>
      </div>
    </form>
  );
}
