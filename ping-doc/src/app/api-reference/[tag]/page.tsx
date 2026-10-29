import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { OperationCard } from "@/components/OperationCard";
import { Toc } from "@/components/Toc";
import { opAnchor, operationsFor, TAGS } from "@/lib/openapi";

type Props = { params: Promise<{ tag: string }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return TAGS.map((t) => ({ tag: t.key }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { tag } = await params;
  const info = TAGS.find((t) => t.key === tag);
  return info ? { title: `${info.title} API`, description: info.description } : {};
}

export default async function TagPage({ params }: Props) {
  const { tag } = await params;
  const info = TAGS.find((t) => t.key === tag);
  if (!info) notFound();
  const ops = operationsFor(tag);

  return (
    <>
      <main className="content">
        <article className="prose">
          <p className="eyebrow">API reference{info.internal ? " · internal" : ""}</p>
          <h1>{info.title}</h1>
          <p className="lead">{info.description}</p>
          {info.internal && (
            <div className="callout callout-warning">
              <p>
                <strong>Internal.</strong> These endpoints are for the Pingie team&apos;s admin console and are not part
                of the public API.
              </p>
            </div>
          )}
        </article>
        {ops.map((op) => (
          <OperationCard key={op.operationId} op={op} tag={info} />
        ))}
      </main>
      <Toc items={ops.map((op) => ({ id: opAnchor(op), text: op.summary, depth: 2 }))} />
    </>
  );
}
