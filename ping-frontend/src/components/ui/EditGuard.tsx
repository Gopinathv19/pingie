"use client";

import { useBot } from "@/components/session/BotProvider";

/** Disables every form control inside for people who can't edit this bot. */
export function EditGuard({ children }: { children: React.ReactNode }) {
  const { bot } = useBot();
  return (
    <fieldset className="edit-guard" disabled={bot.access_role === "viewer"}>
      {children}
    </fieldset>
  );
}
