"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

export interface SearchEntry {
  title: string;
  href: string;
  section: string;
  text: string;
}

function score(e: SearchEntry, terms: string[]): number {
  const title = e.title.toLowerCase();
  const text = e.text.toLowerCase();
  let total = 0;
  for (const t of terms) {
    if (title.includes(t)) total += 10;
    else if (text.includes(t)) total += 1;
    else return 0;
  }
  return total;
}

function snippet(text: string, term: string): string {
  const i = text.toLowerCase().indexOf(term);
  if (i < 0) return text.slice(0, 110);
  const start = Math.max(0, i - 40);
  return (start ? "…" : "") + text.slice(start, start + 120) + "…";
}

export function Search({ index }: { index: SearchEntry[] }) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "/" && !open && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        setOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(() => {
    if (open) setTimeout(() => input.current?.focus(), 10);
    else setQ("");
  }, [open]);

  const terms = q.toLowerCase().split(/\s+/).filter(Boolean);
  const results = useMemo(() => {
    if (!terms.length) return index.slice(0, 8);
    return index
      .map((e) => ({ e, s: score(e, terms) }))
      .filter((r) => r.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 12)
      .map((r) => r.e);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, index]);

  useEffect(() => setActive(0), [q]);

  const go = (href: string) => {
    setOpen(false);
    router.push(href);
  };

  return (
    <>
      <button type="button" className="search-btn" onClick={() => setOpen(true)} aria-label="Search docs">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-3.5-3.5" />
        </svg>
        <span>Search docs</span>
        <kbd>⌘K</kbd>
      </button>
      {open && (
        <div className="search-overlay" onClick={() => setOpen(false)}>
          <div className="search-panel" role="dialog" aria-label="Search" onClick={(e) => e.stopPropagation()}>
            <input
              ref={input}
              className="search-input"
              placeholder="Search guides and API endpoints…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setOpen(false);
                else if (e.key === "ArrowDown") {
                  e.preventDefault();
                  setActive((a) => Math.min(a + 1, results.length - 1));
                } else if (e.key === "ArrowUp") {
                  e.preventDefault();
                  setActive((a) => Math.max(a - 1, 0));
                } else if (e.key === "Enter" && results[active]) go(results[active].href);
              }}
            />
            <ul className="search-results">
              {results.length === 0 && <li className="search-empty">No results for &ldquo;{q}&rdquo;</li>}
              {results.map((r, i) => (
                <li key={r.href + r.title}>
                  <button
                    type="button"
                    className={`search-result${i === active ? " active" : ""}`}
                    onMouseEnter={() => setActive(i)}
                    onClick={() => go(r.href)}
                  >
                    <span className="search-section">{r.section}</span>
                    <strong>{r.title}</strong>
                    {terms[0] && <span className="search-snippet">{snippet(r.text, terms[0])}</span>}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}
