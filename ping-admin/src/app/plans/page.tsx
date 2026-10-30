import Link from "next/link";
import { adminApi } from "@/lib/api";

export const metadata = { title: "Plans" };

const n = (v: number) => (v >= 9999 ? "Unlimited" : v.toLocaleString("en-US"));

export default async function PlansPage({ searchParams }: { searchParams: Promise<{ saved?: string }> }) {
  const { saved } = await searchParams;
  const plans = await adminApi.listPlans();

  return (
    <div style={{ padding: "32px 40px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 20, fontWeight: 700 }}>Plans</h1>
          <p className="muted" style={{ fontSize: 13 }}>
            Public plans appear on the customer pricing page and upgrade modal, in sort order.
          </p>
        </div>
        <Link href="/plans/new" className="btn btn-primary">+ New plan</Link>
      </div>

      {saved && <div className="notice">Plan saved.</div>}

      <div style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
        <table>
          <thead>
            <tr>
              <th>Plan</th>
              <th>Price</th>
              <th>Messages / mo</th>
              <th>Bots</th>
              <th>Sources / bot</th>
              <th>Members</th>
              <th>Shares / bot</th>
              <th>Model tiers</th>
              <th>Flags</th>
              <th>Orgs</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {plans.map((p) => (
              <tr key={p.key} style={{ opacity: p.active ? 1 : 0.5 }}>
                <td>
                  <div style={{ fontWeight: 600, color: "var(--text)" }}>{p.name}</div>
                  <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{p.key} · order {p.sort_order}</div>
                </td>
                <td>{p.price_label || (p.price_monthly === null ? "Custom" : `$${p.price_monthly}`)}</td>
                <td>{n(p.messages_limit)}</td>
                <td>{n(p.bots_limit)}</td>
                <td>{n(p.sources_limit)}</td>
                <td>{n(p.members_limit)}</td>
                <td>{n(p.shares_limit)}</td>
                <td>{p.model_tiers.join(", ")}</td>
                <td style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {p.is_default && <span className="badge badge-paid">Default</span>}
                  {p.highlighted && <span className="badge">Popular</span>}
                  {!p.is_public && <span className="badge">Hidden</span>}
                  {!p.active && <span className="badge badge-off">Archived</span>}
                  {p.remove_branding && <span className="badge">No badge</span>}
                  {p.custom_design && <span className="badge">Custom design</span>}
                </td>
                <td>{p.org_count}</td>
                <td>
                  <Link href={`/plans/${encodeURIComponent(p.key)}`} className="btn">Edit</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
