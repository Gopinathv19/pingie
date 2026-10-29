import Link from "next/link";
import { adminApi } from "@/lib/api";

export const metadata = { title: "Organizations" };

export default async function OrgsPage({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q } = await searchParams;
  const orgs = await adminApi.listOrgs(q ?? undefined);

  return (
    <div style={{ padding: "32px 40px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Organizations</h1>
        <form method="GET" style={{ display: "flex", gap: 8, width: 320 }}>
          <input name="q" defaultValue={q} placeholder="Search by name or email…" />
          <button type="submit" className="btn">Search</button>
        </form>
      </div>

      <div style={{ border: "1px solid var(--border)", background: "var(--surface)" }}>
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Owner</th>
              <th>Plan</th>
              <th>Messages</th>
              <th>Bots</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {orgs.map((org) => (
              <tr key={org.id}>
                <td>
                  <div style={{ fontWeight: 600, color: "var(--text)" }}>{org.name}</div>
                  <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>{org.slug}</div>
                </td>
                <td>
                  <div>{org.owner_name ?? "—"}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{org.owner_email ?? "—"}</div>
                </td>
                <td>
                  <span className={`badge ${org.plan_paid ? "badge-paid" : ""}`}>{org.plan_name}</span>
                </td>
                <td>
                  <span style={{ color: org.messages_used >= org.messages_limit ? "var(--danger-soft)" : undefined }}>
                    {org.messages_used.toLocaleString("en-US")}
                  </span>
                  <span className="muted"> / {org.messages_limit.toLocaleString("en-US")}</span>
                </td>
                <td>
                  {org.bots_used} / {org.bots_limit}
                </td>
                <td className="muted">{new Date(org.created_at).toLocaleDateString("en-US")}</td>
                <td>
                  <Link href={`/orgs/${org.id}`} className="btn">Edit</Link>
                </td>
              </tr>
            ))}
            {orgs.length === 0 && (
              <tr>
                <td colSpan={7} style={{ textAlign: "center", padding: "40px 0", color: "var(--text-3)" }}>
                  No organizations found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="muted" style={{ marginTop: 12, fontSize: 12 }}>
        {orgs.length} organization{orgs.length !== 1 ? "s" : ""} found.
      </div>
    </div>
  );
}
