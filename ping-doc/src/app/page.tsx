import { notFound } from "next/navigation";
import { DocPage } from "@/components/DocPage";
import { getDoc } from "@/lib/content";

export default function Home() {
  const doc = getDoc("/");
  if (!doc) notFound();
  return <DocPage doc={doc} />;
}
