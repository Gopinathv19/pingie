import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { DocPage } from "@/components/DocPage";
import { getDoc, guideHrefs } from "@/lib/content";

type Props = { params: Promise<{ slug: string[] }> };

export const dynamicParams = false;

export function generateStaticParams() {
  return guideHrefs()
    .filter((h) => h !== "/")
    .map((h) => ({ slug: h.slice(1).split("/") }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const doc = getDoc(`/${slug.join("/")}`);
  return doc ? { title: doc.title, description: doc.description } : {};
}

export default async function GuidePage({ params }: Props) {
  const { slug } = await params;
  const doc = getDoc(`/${slug.join("/")}`);
  if (!doc) notFound();
  return <DocPage doc={doc} />;
}
