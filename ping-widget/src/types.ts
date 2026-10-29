// Shapes of the public widget API (ping-backend/app/schemas/widget.py).

export interface Appearance {
  title: string;
  welcome: string;
  placeholder: string;
  accent: string;
  position: "right" | "left";
  launcher: "chat" | "spark" | "help";
  suggestions: string[];
  show_sources: boolean;
  show_branding: boolean;
  theme: "dark" | "light";
}

export interface WidgetConfig {
  bot_id: string;
  name: string;
  status: "live" | "paused" | "draft";
  online: boolean;
  agents_online?: boolean;
  appearance: Appearance;
}

export interface Citation {
  source_id?: string | null;
  source_name: string;
  location?: string;
  chunk_id?: string | null;
  score?: number | null;
}

/** answered | partial | fallback from reasoning; offline and lead from the chat service. */
export type Outcome = "answered" | "partial" | "fallback" | "offline" | "lead" | string;

/** Who is answering: the bot, a person (or about to be), or nobody. */
export type ChatStatus = "bot" | "waiting" | "human" | "closed";

export interface BotReply {
  message_id: string | null; // null when a person is handling the chat
  text: string;
  outcome: Outcome;
  citations: Citation[];
  asks_for_email: boolean;
  offer_human?: boolean;
  status?: ChatStatus;
}

export interface LiveMessage {
  id: string;
  role: "agent" | "system";
  content: string;
  created_at: string;
  author_name: string | null;
  asks_for_email: boolean;
}

export interface LiveUpdates {
  status: ChatStatus;
  agent: { name: string; avatar_url: string } | null;
  messages: LiveMessage[];
}

export interface ConversationStarted {
  conversation_id: string;
  token: string;
}

/** A message as the widget keeps it (and stores it in localStorage). */
export interface ChatMessage {
  id: string;
  role: "visitor" | "bot" | "agent" | "system";
  text: string;
  messageId?: string; // server id: needed for feedback, and to de-duplicate polled messages
  authorName?: string; // agent messages
  offerHuman?: boolean; // bot fallback with someone online to take over
  outcome?: Outcome;
  citations?: Citation[];
  asksForEmail?: boolean;
  feedback?: "up" | "down";
  pending?: boolean; // still streaming
  statusText?: string; // shown with the typing dots until the first words arrive
  error?: boolean; // a local error notice, never sent by the server
}
