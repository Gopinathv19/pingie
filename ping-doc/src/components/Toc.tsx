"use client";

import { useEffect, useState } from "react";

export interface TocItem {
  id: string;
  text: string;
  depth: number;
}

export function Toc({ items }: { items: TocItem[] }) {
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const els = items.map((i) => document.getElementById(i.id)).filter(Boolean) as HTMLElement[];
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-70px 0px -70% 0px" },
    );
    els.forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, [items]);

  if (items.length < 2) return null;
  return (
    <aside className="toc" aria-label="On this page">
      <div className="toc-title">On this page</div>
      {items.map((i) => (
        <a key={i.id} href={`#${i.id}`} className={`toc-link depth-${i.depth}${active === i.id ? " active" : ""}`}>
          {i.text}
        </a>
      ))}
    </aside>
  );
}
