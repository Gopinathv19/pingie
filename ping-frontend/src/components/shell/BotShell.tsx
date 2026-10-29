"use client";

import { BotProvider, useBot } from "@/components/session/BotProvider";
import { SessionProvider } from "@/components/session/SessionProvider";
import { Icon } from "@/components/Icon";
import { LiveProvider } from "@/components/live/LiveProvider";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import s from "./shell.module.css";

function Frame({ children }: { children: React.ReactNode }) {
  const { bot } = useBot();
  return (
    <>
      <Topbar bot={bot} />
      <div className={s.body}>
        <aside className={s.sidebarCol}>
          <Sidebar bot={bot} />
        </aside>
        <main className={s.main}>
          {bot.access_role === "viewer" && (
            <div className={s.readOnly} role="note">
              <Icon name="help" size={14} />
              View only. {bot.access_via === "share" ? "This bot was shared with you" : "You're a viewer in this workspace"}
              {" "}from {bot.organization_name}; ask the owner for edit access to make changes.
            </div>
          )}
          {children}
        </main>
      </div>
    </>
  );
}

export function BotShell({ botId, children }: { botId: string; children: React.ReactNode }) {
  return (
    <div className={s.app}>
      <SessionProvider>
        <LiveProvider>
          <BotProvider botId={botId}>
            <Frame>{children}</Frame>
          </BotProvider>
        </LiveProvider>
      </SessionProvider>
    </div>
  );
}

export function OrgShell({ children }: { children: React.ReactNode }) {
  return (
    <div className={s.app}>
      <SessionProvider>
        <LiveProvider>
          <Topbar />
          <main className={s.mainWide}>{children}</main>
        </LiveProvider>
      </SessionProvider>
    </div>
  );
}
