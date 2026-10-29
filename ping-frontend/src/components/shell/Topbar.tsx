"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { UpgradeModal } from "@/components/billing/UpgradeModal";
import { conversationHref, useLive } from "@/components/live/LiveProvider";
import { useSession } from "@/components/session/SessionProvider";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { botHref } from "@/lib/nav";
import { type ThemePref, useTheme } from "@/lib/theme";
import type { Bot, BotStatus, BotSummary } from "@/lib/types";
import { useDismiss } from "@/lib/use-dismiss";
import { CommandPalette } from "./CommandPalette";
import s from "./shell.module.css";

const DOCS_URL = process.env.NEXT_PUBLIC_DOCS_URL || "http://localhost:3003";

type MenuKey = "org" | "bot" | "account" | "live" | null;

function userInitials(name: string, email: string) {
  const parts = (name || email).split(/[\s@.]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts[1]?.[0] ?? "")).toUpperCase();
}

export function Topbar({ bot }: { bot?: Bot }) {
  const { user, org, orgs, switchOrg } = useSession();
  const sharedBot = bot?.access_via === "share";
  const [menu, setMenu] = useState<MenuKey>(null);
  const [showUpgrade, setShowUpgrade] = useState(false);
  const { pref, setPref } = useTheme();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [bots, setBots] = useState<BotSummary[] | null>(null);
  const close = useCallback(() => setMenu(null), []);
  const orgRef = useDismiss<HTMLDivElement>(menu === "org", close);
  const botRef = useDismiss<HTMLDivElement>(menu === "bot", close);
  const accountRef = useDismiss<HTMLDivElement>(menu === "account", close);
  const liveRef = useDismiss<HTMLDivElement>(menu === "live", close);
  const live = useLive();
  const toggle = (key: MenuKey) => setMenu((m) => (m === key ? null : key));

  // The bot list feeds the switcher and the palette; fetch it when first needed.
  const needBots = menu === "bot" || paletteOpen;
  useEffect(() => {
    if (needBots && bots === null) api.orgs.bots(org.id).then(setBots, () => setBots([]));
  }, [needBots, bots, org.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const logout = async () => {
    try {
      await api.auth.logout();
    } finally {
      window.location.href = "/login";
    }
  };

  return (
    <header className={s.topbar}>
      <nav aria-label="Breadcrumb" className={s.crumbs}>
        <Link href="/bots" className={s.brand}>
          <span aria-hidden="true" className={s.brandMark}>
            P
          </span>
          Pingie
        </Link>
        <span aria-hidden="true" className={s.slash}>
          /
        </span>

        {sharedBot && (
          <Link href="/bots" className={s.switcher} title={`Shared from ${bot.organization_name}`}>
            Shared with me
          </Link>
        )}
        <div ref={orgRef} className={s.switcherWrap} style={sharedBot ? { display: "none" } : undefined}>
          <button
            type="button"
            aria-label="Switch organization"
            aria-expanded={menu === "org"}
            className={s.switcher}
            onClick={() => toggle("org")}
          >
            <span aria-hidden="true" className={s.orgMark}>
              {org.initial}
            </span>
            {org.name}
            <span className={s.planTag}>{org.plan_name}</span>
            <Icon name="chevrons" size={12} strokeWidth={2.2} style={{ color: "var(--text-4)" }} />
          </button>
          {menu === "org" && (
            <div className={s.menu} role="menu">
              <div className={s.menuLabel}>Workspaces</div>
              {orgs.map((o) => (
                <button
                  key={o.id}
                  type="button"
                  role="menuitem"
                  className={`${s.menuItem} ${o.id === org.id ? s.menuItemActive : ""}`}
                  onClick={() => (o.id === org.id ? close() : switchOrg(o.id))}
                >
                  <span className={s.orgMark}>{o.initial}</span>
                  {o.name}
                  <span className={s.menuMeta}>{o.role}</span>
                  {o.id === org.id && <Icon name="check" size={14} style={{ color: "var(--accent-soft)" }} />}
                </button>
              ))}
              <div className={s.menuSep} />
              <Link href="/settings/members" role="menuitem" className={s.menuItem} onClick={close}>
                <Icon name="conversations" size={14} />
                Members & invites
              </Link>
              <Link href="/settings/billing" role="menuitem" className={s.menuItem} onClick={close}>
                <Icon name="spark" size={14} />
                Plan & billing
              </Link>
              <div className={s.menuSep} />
              <div style={{ padding: "8px 12px", fontSize: 12 }} className="muted">
                {org.usage.messages_used.toLocaleString("en-US")} / {org.usage.messages_limit.toLocaleString("en-US")}{" "}
                messages this month
              </div>
            </div>
          )}
        </div>

        {bot && (
          <>
            <span aria-hidden="true" className={s.slash}>
              /
            </span>
            <div ref={botRef} className={s.switcherWrap}>
              <button
                type="button"
                aria-label="Switch bot"
                aria-expanded={menu === "bot"}
                className={`${s.switcher} ${s.switcherBoxed}`}
                onClick={() => toggle("bot")}
              >
                <span aria-hidden="true" className="dot" style={{ background: dotColor(bot.status) }} />
                {bot.name}
                <Icon name="chevrons" size={12} strokeWidth={2.2} style={{ color: "var(--text-4)" }} />
              </button>
              {menu === "bot" && (
                <div className={s.menu} role="menu">
                  <div className={s.menuLabel}>Bots</div>
                  {bots === null && <div style={{ padding: "8px 12px", fontSize: 12 }} className="muted">Loading…</div>}
                  {bots?.map((b) => (
                    <Link
                      key={b.id}
                      href={botHref(b.id)}
                      role="menuitem"
                      className={`${s.menuItem} ${b.id === bot.id ? s.menuItemActive : ""}`}
                      onClick={close}
                    >
                      <span className="dot" style={{ background: dotColor(b.status) }} />
                      {b.name}
                      <span className={s.menuMeta}>{b.id}</span>
                    </Link>
                  ))}
                  <div className={s.menuSep} />
                  <Link href="/bots/new" role="menuitem" className={s.menuItem} onClick={close}>
                    <Icon name="plus" size={14} />
                    New bot
                  </Link>
                </div>
              )}
            </div>
          </>
        )}
      </nav>

      <div className={s.right}>
        <button type="button" className={s.search} onClick={() => setPaletteOpen(true)}>
          <Icon name="test" size={13} strokeWidth={2} />
          Search
          <span className={s.kbd}>⌘K</span>
        </button>
        <a href={DOCS_URL} target="_blank" rel="noreferrer" className={s.navLink}>
          Docs
        </a>
        <a href="#" className={s.navLink}>
          Support
        </a>
        {showUpgrade && <UpgradeModal onClose={() => setShowUpgrade(false)} />}
        {org.can_upgrade && (
          <button
            type="button"
            className="btn btn-sm btn-primary"
            onClick={() => setShowUpgrade(true)}
          >
            <Icon name="spark" size={12} />
            Upgrade
          </button>
        )}
        <div ref={liveRef} className={s.switcherWrap}>
          <button
            type="button"
            className={`${s.liveBtn} ${live.waiting.length ? s.liveBtnAlert : ""}`}
            aria-expanded={menu === "live"}
            aria-label={`Live chats: ${live.waiting.length} waiting`}
            onClick={() => toggle("live")}
          >
            <span className={`${s.presenceDot} ${live.available ? s.presenceOn : ""}`} aria-hidden="true" />
            Live
            {live.waiting.length > 0 && <span className={s.liveCount}>{live.waiting.length}</span>}
          </button>
          {menu === "live" && (
            <div className={`${s.menu} ${s.menuRight}`} role="menu" style={{ minWidth: 300 }}>
              <label className={s.menuItem} style={{ cursor: "pointer" }}>
                <span className={`${s.presenceDot} ${live.available ? s.presenceOn : ""}`} aria-hidden="true" />
                {live.available ? "Available for live chat" : "Away"}
                <input
                  type="checkbox"
                  style={{ marginLeft: "auto" }}
                  checked={live.available}
                  onChange={(e) => live.setAvailable(e.target.checked)}
                  aria-label="Available for live chat"
                />
              </label>
              <div style={{ padding: "0 12px 8px", fontSize: 11.5 }} className="subtle">
                {live.available
                  ? "Visitors can ask for you when the bot can't answer. Keep this tab open."
                  : "Turn on to get chats when the bot can't answer."}
              </div>
              <div className={s.menuSep} />
              <div className={s.menuLabel}>Waiting ({live.waiting.length})</div>
              {live.waiting.length === 0 && (
                <div style={{ padding: "4px 12px 10px", fontSize: 12 }} className="muted">
                  Nobody is waiting.
                </div>
              )}
              {live.waiting.map((w) => (
                <Link key={w.conversation_id} href={conversationHref(w)} role="menuitem" className={s.menuItem} onClick={close}>
                  <span className="dot" style={{ background: "var(--warn)" }} />
                  <span style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                    <strong style={{ fontWeight: 600 }}>{w.visitor}</strong>
                    <span className="subtle" style={{ fontSize: 11 }}>{w.bot_name}</span>
                  </span>
                  <span className={s.menuMeta}>{w.waiting_since ? relativeTime(w.waiting_since) : ""}</span>
                </Link>
              ))}
              {live.mine.length > 0 && (
                <>
                  <div className={s.menuSep} />
                  <div className={s.menuLabel}>Your chats ({live.mine.length})</div>
                  {live.mine.map((w) => (
                    <Link key={w.conversation_id} href={conversationHref(w)} role="menuitem" className={s.menuItem} onClick={close}>
                      <span className="dot" style={{ background: "var(--accent)" }} />
                      {w.visitor}
                      <span className={s.menuMeta}>{w.bot_name}</span>
                    </Link>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
        <ThemeButton pref={pref} setPref={setPref} />
        <div ref={accountRef} className={s.switcherWrap}>
          <button
            type="button"
            aria-label="Account menu"
            aria-expanded={menu === "account"}
            className={s.avatar}
            onClick={() => toggle("account")}
            style={
              user.avatar_url
                ? { backgroundImage: `url(${user.avatar_url})`, backgroundSize: "cover", color: "transparent" }
                : undefined
            }
          >
            {userInitials(user.name, user.email)}
          </button>
          {menu === "account" && (
            <div className={`${s.menu} ${s.menuRight}`} role="menu">
              <div style={{ padding: "8px 12px" }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{user.name || user.email}</div>
                <div className="subtle" style={{ fontSize: 12, marginTop: 2 }}>
                  {user.email}
                </div>
              </div>
              <div className={s.menuSep} />
              <div className={s.menuLabel}>Theme</div>
              <div style={{ padding: "4px 12px 8px" }}>
                <div role="group" aria-label="Theme" className="segmented">
                  {(["dark", "light", "system"] as const).map((t) => (
                    <button key={t} type="button" aria-pressed={pref === t} onClick={() => setPref(t)}>
                      {t[0].toUpperCase() + t.slice(1)}
                    </button>
                  ))}
                </div>
              </div>
              <div className={s.menuSep} />
              <button type="button" role="menuitem" className={s.menuItem} onClick={logout}>
                Log out
              </button>
            </div>
          )}
        </div>
      </div>

      {paletteOpen && <CommandPalette bot={bot} bots={bots ?? []} onClose={() => setPaletteOpen(false)} />}
    </header>
  );
}

function ThemeButton({ pref, setPref }: { pref: ThemePref; setPref: (p: ThemePref) => void }) {
  // "system" resolves at runtime, so read what is actually applied.
  const [isLight, setIsLight] = useState(false);
  useEffect(() => {
    setIsLight(document.documentElement.dataset.theme === "light");
  }, [pref]);
  const label = isLight ? "Switch to dark mode" : "Switch to light mode";
  return (
    <button
      type="button"
      className={s.iconButton}
      aria-label={label}
      title={label}
      onClick={() => setPref(isLight ? "dark" : "light")}
    >
      <Icon name={isLight ? "moon" : "sun"} size={15} />
    </button>
  );
}

function dotColor(status: BotStatus) {
  if (status === "live") return "var(--ok)";
  if (status === "paused") return "var(--warn)";
  return "var(--text-4)";
}
