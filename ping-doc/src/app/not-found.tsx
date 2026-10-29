import Link from "next/link";

export default function NotFound() {
  return (
    <main className="content">
      <article className="prose">
        <p className="eyebrow">404</p>
        <h1>Page not found</h1>
        <p className="lead">That page doesn&apos;t exist. Try the search (⌘K) or start from the introduction.</p>
        <p>
          <Link href="/">Back to the docs</Link>
        </p>
      </article>
    </main>
  );
}
