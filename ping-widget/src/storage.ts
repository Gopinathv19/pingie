import type { ChatMessage, ChatStatus } from "./types";

// localStorage can be missing or throw (private mode, blocked site data,
// sandboxed iframes). Every access goes through these, and the widget still
// works without it -- it just forgets the chat on reload.

const memory = new Map<string, string>();

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return memory.get(key) ?? null;
  }
}

function write(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    if (value === null) memory.delete(key);
    else memory.set(key, value);
  }
}

function randomId(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** The anonymous id that makes a returning visitor the same visitor. */
export function visitorId(): string {
  const key = "pingie:visitor";
  let id = read(key);
  if (!id || !/^[A-Za-z0-9_-]{8,64}$/.test(id)) {
    id = randomId();
    write(key, id);
  }
  return id;
}

export interface SavedChat {
  conversationId: string;
  token: string;
  messages: ChatMessage[];
  open: boolean;
  savedAt: number;
  status?: ChatStatus;
  agentName?: string;
  lastLiveAt?: string; // created_at of the newest agent/system message seen
}

const MAX_MESSAGES = 60;
// The backend's conversation token lives 30 days; start fresh well before.
const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

const chatKey = (botId: string) => `pingie:chat:${botId}`;

export function loadChat(botId: string): SavedChat | null {
  const raw = read(chatKey(botId));
  if (!raw) return null;
  try {
    const chat = JSON.parse(raw) as SavedChat;
    if (!chat.conversationId || !chat.token || Date.now() - chat.savedAt > MAX_AGE_MS) return null;
    return chat;
  } catch {
    return null;
  }
}

export function saveChat(botId: string, chat: SavedChat | null): void {
  if (!chat) return write(chatKey(botId), null);
  const messages = chat.messages.filter((m) => !m.pending && !m.error).slice(-MAX_MESSAGES);
  write(chatKey(botId), JSON.stringify({ ...chat, messages, savedAt: Date.now() }));
}

export const newLocalId = randomId;
