"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { botHref, visibleNav } from "@/lib/nav";
import type { Bot, BotSummary } from "@/lib/types";
import s from "./shell.module.css";

interface Command {
  id: string;
  label: string;
  group: string;
  icon: IconName;
  href: string;
}

export function CommandPalette({ bot, bots, onClose }: { bot?: Bot; bots: BotSummary[]; onClose: () => void }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);

  const commands = useMemo<Command[]>(() => {
    const list: Command[] = [];
    if (bot) {
      for (const g of visibleNav(bot.access_role))
        for (const item of g.items)
          list.push({ id: item.key, label: item.label, group: bot.name, icon: item.icon, href: botHref(bot.id, item.segment) });
    }
    for (const b of bots)
      list.push({ id: b.id, label: b.name, group: "Bots", icon: "conversations", href: botHref(b.id) });
    list.push({ id: "all", label: "All bots", group: "Navigate", icon: "overview", href: "/bots" });
    list.push({ id: "members", label: "Members & invites", group: "Navigate", icon: "conversations", href: "/settings/members" });
    list.push({ id: "billing", label: "Plan & billing", group: "Navigate", icon: "spark", href: "/settings/billing" });
    list.push({ id: "new", label: "Create a new bot", group: "Navigate", icon: "plus", href: "/bots/new" });
    return list;
  }, [bot, bots]);

  const q = query.trim().toLowerCase();
  const results = q ? commands.filter((c) => c.label.toLowerCase().includes(q)) : commands;
  const go = (c: Command | undefined) => {
    if (!c) return;
    router.push(c.href);
    onClose();
  };

  return (
    <div className={s.overlay} onPointerDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={s.palette} role="dialog" aria-label="Search">
        <div className={s.paletteInput}>
          <Icon name="test" size={15} />
          <input
            autoFocus
            placeholder="Search pages and bots…"
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(a + 1, results.length - 1));
              }
              if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(a - 1, 0));
              }
              if (e.key === "Enter") go(results[active]);
            }}
          />
          <span className={s.kbd}>ESC</span>
        </div>
        <div className={s.paletteList} role="listbox">
          {results.length === 0 && <div className="empty">No results for “{query}”</div>}
          {results.map((c, i) => (
            <button
              key={c.group + c.id}
              type="button"
              role="option"
              aria-selected={i === active}
              className={`${s.menuItem} ${i === active ? s.paletteItemActive : ""}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => go(c)}
            >
              <Icon name={c.icon} size={15} style={{ color: "var(--text-4)" }} />
              {c.label}
              <span className={s.menuMeta}>{c.group}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
