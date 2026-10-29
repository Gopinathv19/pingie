"use client";

import Link from "next/link";
import { createContext, useContext } from "react";
import { api } from "@/lib/api";
import type { Bot } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { ErrorState, Loading } from "@/components/ui/States";

interface BotContextValue {
  bot: Bot;
  reload: () => void;
  setBot: (bot: Bot) => void;
}

const BotContext = createContext<BotContextValue | null>(null);

export function BotProvider({ botId, children }: { botId: string; children: React.ReactNode }) {
  const { data, error, reload, setData } = useApi(() => api.bots.get(botId), [botId]);

  if (error?.status === 404) {
    return (
      <div className="empty" style={{ padding: 80 }}>
        <h1 style={{ margin: "0 0 8px", fontSize: 22, color: "var(--text)" }}>Bot not found</h1>
        <p>It doesn&apos;t exist, or you don&apos;t have access.</p>
        <Link href="/bots" className="btn" style={{ marginTop: 12 }}>
          Back to bots
        </Link>
      </div>
    );
  }
  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!data) return <Loading height={320} />;
  return <BotContext.Provider value={{ bot: data, reload, setBot: setData }}>{children}</BotContext.Provider>;
}

export function useBot(): BotContextValue {
  const ctx = useContext(BotContext);
  if (!ctx) throw new Error("useBot outside BotProvider");
  return ctx;
}
