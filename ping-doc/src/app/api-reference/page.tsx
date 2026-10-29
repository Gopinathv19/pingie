import Link from "next/link";
import { counts, TAGS } from "@/lib/openapi";

export const metadata = { title: "API reference" };

export default function ApiReferenceIndex() {
  const c = counts();
  return (
    <main className="content wide">
      <article className="prose">
        <h1>API reference</h1>
        <p className="lead">
          Every endpoint of the Pingie REST API ({c.operations} operations), generated from the backend&apos;s OpenAPI
          schema. All paths are under <code>/api/v1</code>. Read the <Link href="/api/overview">API overview</Link> first
          for authentication, errors and streaming.
        </p>
      </article>
      <div className="tag-grid">
        {TAGS.map((t) => (
          <Link key={t.key} href={`/api-reference/${t.key}`} className="tag-card">
            <span className="tag-card-head">
              <strong>{t.title}</strong>
              <span className="muted">{c.byTag[t.key]} endpoints</span>
            </span>
            <span className="tag-card-desc">{t.description}</span>
            <span className={`auth auth-${t.auth}`}>{t.auth === "none" ? "public" : t.auth}</span>
          </Link>
        ))}
      </div>
    </main>
  );
}
