import Link from "next/link";

export default function NotFound() {
  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div style={{ textAlign: "center", display: "flex", flexDirection: "column", gap: 12, alignItems: "center" }}>
        <span className="mono subtle" style={{ fontSize: 12 }}>404</span>
        <h1 style={{ margin: 0, fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em" }}>Page not found</h1>
        <p className="muted" style={{ margin: 0, fontSize: 14 }}>That bot or page doesn&apos;t exist, or you don&apos;t have access.</p>
        <Link href="/bots" className="btn" style={{ marginTop: 8 }}>Back to bots</Link>
      </div>
    </div>
  );
}
