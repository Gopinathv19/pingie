import Link from "next/link";
import type { Doc } from "@/lib/content";
import { neighbours } from "@/lib/nav";
import { Toc } from "./Toc";

export function DocPage({ doc }: { doc: Doc }) {
  const { prev, next } = neighbours(doc.href);
  return (
    <>
      <main className="content">
        <article className="prose">
          <h1>{doc.title}</h1>
          {doc.description && <p className="lead">{doc.description}</p>}
          <div dangerouslySetInnerHTML={{ __html: doc.html }} />
        </article>
        <nav className="pager" aria-label="Pagination">
          {prev ? (
            <Link href={prev.href} className="pager-link">
              <span>Previous</span>
              {prev.title}
            </Link>
          ) : (
            <span />
          )}
          {next && (
            <Link href={next.href} className="pager-link next">
              <span>Next</span>
              {next.title}
            </Link>
          )}
        </nav>
      </main>
      <Toc items={doc.headings} />
    </>
  );
}
