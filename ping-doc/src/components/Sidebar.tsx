"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV } from "@/lib/nav";
import { TAGS } from "@/lib/openapi";

export function Sidebar() {
  const pathname = usePathname();
  const inReference = pathname.startsWith("/api-reference");

  return (
    <nav className="sidebar" aria-label="Documentation">
      {NAV.map((section) => (
        <div key={section.title} className="nav-section">
          <div className="nav-title">
            {section.title}
            {section.internal && <span className="pill">team</span>}
          </div>
          {section.items.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname === item.href;
            return (
              <div key={item.href}>
                <Link href={item.href} className={`nav-link${active ? " active" : ""}`} aria-current={active ? "page" : undefined}>
                  {item.title}
                </Link>
                {item.href === "/api-reference" && inReference && (
                  <div className="nav-sub">
                    {TAGS.map((t) => {
                      const href = `/api-reference/${t.key}`;
                      return (
                        <Link key={t.key} href={href} className={`nav-link small${pathname === href ? " active" : ""}`}>
                          {t.title}
                        </Link>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
