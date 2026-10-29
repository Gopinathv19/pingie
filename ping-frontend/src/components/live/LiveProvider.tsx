"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { LiveItem } from "@/lib/types";

const AVAILABLE_KEY = "pingie-available";
const POLL_MS = 5000;
const HEARTBEAT_MS = 30000;

interface Live {
  available: boolean;
  setAvailable: (v: boolean) => void;
  waiting: LiveItem[];
  mine: LiveItem[];
}

const LiveContext = createContext<Live>({ available: false, setAvailable: () => {}, waiting: [], mine: [] });

export const conversationHref = (item: Pick<LiveItem, "bot_id" | "conversation_id">) =>
  `/bots/${item.bot_id}/conversations?c=${item.conversation_id}`;

function chime() {
  try {
    const ctx = new AudioContext();
    [880, 1320].forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = freq;
      osc.connect(gain);
      gain.connect(ctx.destination);
      const t = ctx.currentTime + i * 0.16;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(0.2, t + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
      osc.start(t);
      osc.stop(t + 0.32);
    });
    setTimeout(() => ctx.close(), 800);
  } catch {
    /* audio blocked until the user interacts with the page */
  }
}

function notify(item: LiveItem) {
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
  const n = new Notification(`${item.visitor} wants to talk to a person`, {
    body: `${item.bot_name} · open the chat to reply`,
    tag: item.conversation_id,
  });
  n.onclick = () => {
    window.focus();
    window.location.href = conversationHref(item);
    n.close();
  };
}

/** Presence heartbeat, the waiting-chats poll, and alerts for new ones. */
export function LiveProvider({ children }: { children: React.ReactNode }) {
  const [available, setAvailableState] = useState(false);
  const [waiting, setWaiting] = useState<LiveItem[]>([]);
  const [mine, setMine] = useState<LiveItem[]>([]);
  const seen = useRef<Set<string> | null>(null);
  const availableRef = useRef(false);
  availableRef.current = available;

  useEffect(() => {
    setAvailableState(localStorage.getItem(AVAILABLE_KEY) === "1");
  }, []);

  const setAvailable = useCallback((v: boolean) => {
    localStorage.setItem(AVAILABLE_KEY, v ? "1" : "0");
    setAvailableState(v);
    if (v && typeof Notification !== "undefined" && Notification.permission === "default") {
      void Notification.requestPermission();
    }
    api.live.presence(v).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!available) return;
    const beat = () => api.live.presence(true).catch(() => undefined);
    beat();
    const t = setInterval(beat, HEARTBEAT_MS);
    return () => clearInterval(t);
  }, [available]);

  useEffect(() => {
    let stopped = false;
    const load = async () => {
      if (document.hidden && !availableRef.current) return;
      try {
        const s = await api.live.summary();
        if (stopped) return;
        setWaiting(s.waiting);
        setMine(s.mine);
        const ids = new Set(s.waiting.map((w) => w.conversation_id));
        if (seen.current && availableRef.current) {
          const fresh = s.waiting.filter((w) => !seen.current!.has(w.conversation_id));
          if (fresh.length) {
            chime();
            fresh.forEach(notify);
          }
        }
        seen.current = ids;
      } catch {
        /* keep the last known list */
      }
    };
    load();
    const t = setInterval(load, POLL_MS);
    return () => {
      stopped = true;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    const base = document.title.replace(/^\(\d+\) /, "");
    document.title = waiting.length ? `(${waiting.length}) ${base}` : base;
  }, [waiting.length]);

  return <LiveContext.Provider value={{ available, setAvailable, waiting, mine }}>{children}</LiveContext.Provider>;
}

export function useLive(): Live {
  return useContext(LiveContext);
}
