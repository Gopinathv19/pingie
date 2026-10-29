"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/Icon";
import { useLive } from "@/components/live/LiveProvider";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { botHref, visibleNav } from "@/lib/nav";
import type { Bot } from "@/lib/types";
import s from "./shell.module.css";

export function Sidebar({ bot }: { bot: Bot }) {
  const pathname = usePathname();
  const base = botHref(bot.id);
  const waiting = useLive().waiting.filter((w) => w.bot_id === bot.id).length;

  return (
    <nav aria-label="Bot navigation" className={s.sidebar}>
      <Link href="/bots" className={s.back}>
        <Icon name="back" size={14} strokeWidth={2.2} />
        All bots
      </Link>

      <div className={s.botCard}>
        <span aria-hidden="true" className={s.botMark} style={{ background: bot.color }}>
          {bot.initials}
        </span>
        <span className={s.botMeta}>
          <span className={s.botName}>{bot.name}</span>
          <span className={s.botSub}>
            <StatusBadge status={bot.status} />
            <span className={s.botId}>{bot.id}</span>
          </span>
        </span>
      </div>

      {visibleNav(bot.access_role).map((group) => (
        <div key={group.label} className={s.group}>
          <div className={s.groupLabel}>{group.label}</div>
          {group.items.map((item) => {
            const href = botHref(bot.id, item.segment);
            const active = item.segment ? pathname.startsWith(href) : pathname === base;
            return (
              <Link
                key={item.key}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`${s.item} ${active ? s.itemActive : ""}`}
              >
                <Icon name={item.icon} />
                <span className={s.itemLabel}>{item.label}</span>
                {item.key === "conversations" && waiting > 0 ? (
                  <span className={`${s.itemBadge} ${s.itemBadgeLive}`}>{waiting} waiting</span>
                ) : item.count && bot.counts[item.count] > 0 && (
                  <span className={s.itemBadge}>{bot.counts[item.count].toLocaleString("en-US")}</span>
                )}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
