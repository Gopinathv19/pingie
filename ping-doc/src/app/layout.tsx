import type { Metadata } from "next";
import Link from "next/link";
import { CopyButtons } from "@/components/CopyButtons";
import { Search, type SearchEntry } from "@/components/Search";
import { Sidebar } from "@/components/Sidebar";
import { ThemeToggle } from "@/components/ThemeToggle";
import { getDoc, guideHrefs } from "@/lib/content";
import { NAV } from "@/lib/nav";
import { allOperations, opAnchor, TAGS } from "@/lib/openapi";
import { THEME_SCRIPT } from "@/lib/theme-script";
import "./globals.css";

import Script from "next/script";




export const metadata: Metadata = {
  title: { default: "Pingie Docs", template: "%s · Pingie Docs" },
  description: "Guides and API reference for Pingie, AI support bots that answer from your docs.",
};

function searchIndex(): SearchEntry[] {
  const sectionOf = (href: string) => NAV.find((s) => s.items.some((i) => i.href === href))?.title ?? "Docs";
  const entries: SearchEntry[] = [];
  for (const href of guideHrefs()) {
    const doc = getDoc(href);
    if (!doc) continue;
    entries.push({ title: doc.title, href, section: sectionOf(href), text: `${doc.description} ${doc.text}`.slice(0, 4000) });
    for (const h of doc.headings) entries.push({ title: h.text, href: `${href}#${h.id}`, section: doc.title, text: "" });
  }
  for (const op of allOperations()) {
    const tag = TAGS.find((t) => t.key === op.tag);
    entries.push({
      title: `${op.method.toUpperCase()} ${op.path.replace("/api/v1", "")}`,
      href: `/api-reference/${op.tag}#${opAnchor(op)}`,
      section: `API · ${tag?.title ?? op.tag}`,
      text: `${op.summary} ${op.description}`,
    });
  }
  return entries;
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body>
        <header className="header">
          <Link href="/" className="brand">
            <span className="brand-mark" aria-hidden="true">
              P
            </span>
            Pingie <span className="brand-sub">Docs</span>
          </Link>
          <Search index={searchIndex()} />
          <nav className="header-links" aria-label="Site">
            <Link href="/api-reference">API reference</Link>
            <a href="https://pingie.app" target="_blank" rel="noreferrer">
              Dashboard ↗
            </a>
          </nav>
          <ThemeToggle />
        </header>
        <div className="shell">
          <Sidebar />
          {children}
        </div>
        <CopyButtons />
        // app/layout.tsx


<Script
  src="http://localhost:8080/widget.js"
  data-bot-id="bot_w4o8zt3"
  strategy="lazyOnload"
/>
      </body>
    </html>
  );
}
