import type { BotReply, ConversationStarted, LiveUpdates, WidgetConfig } from "./types";

/** An HTTP error from ping-backend. `detail` and `code` come from its error body. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export interface StreamHandlers {
  onDelta: (text: string) => void;
  /** Progress before the first words, e.g. "Searching the docs…". */
  onStatus?: (text: string) => void;
}

/** Client for /api/v1/widget/{botId}/*. No cookies: a conversation is proven
 * by the X-Conversation-Token issued when it started. */
export class WidgetApi {
  private readonly base: string;

  constructor(apiBase: string, botId: string) {
    this.base = `${apiBase.replace(/\/$/, "")}/api/v1/widget/${encodeURIComponent(botId)}`;
  }

  config(): Promise<WidgetConfig> {
    return this.request("GET", "/config");
  }

  start(visitorId: string, pageUrl: string): Promise<ConversationStarted> {
    return this.request("POST", "/conversations", { visitor_id: visitorId, page_url: pageUrl.slice(0, 2048) });
  }

  feedback(conversationId: string, token: string, messageId: string, value: "up" | "down"): Promise<void> {
    return this.request("POST", `/conversations/${conversationId}/messages/${messageId}/feedback`, { value }, token);
  }

  identify(conversationId: string, token: string, email?: string, name?: string): Promise<void> {
    return this.request("POST", `/conversations/${conversationId}/identify`, { email, name }, token);
  }

  /** Ask for a person. `waiting` when someone is online, else `unavailable`. */
  handoff(conversationId: string, token: string): Promise<{ status: "waiting" | "human" | "unavailable" }> {
    return this.request("POST", `/conversations/${conversationId}/handoff`, {}, token);
  }

  /** Agent and system messages newer than `after`, plus who is answering. */
  updates(conversationId: string, token: string, after?: string): Promise<LiveUpdates> {
    const q = after ? `?after=${encodeURIComponent(after)}` : "";
    return this.request("GET", `/conversations/${conversationId}/updates${q}`, undefined, token);
  }

  /** Send a message and read the streamed reply: `delta` events carry text,
   * the final `done` event carries the stored message. EventSource cannot
   * POST or send headers, so this reads the SSE body from fetch by hand. */
  async send(conversationId: string, token: string, text: string, handlers: StreamHandlers): Promise<BotReply> {
    const res = await fetch(`${this.base}/conversations/${conversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Conversation-Token": token },
      body: JSON.stringify({ text, stream: true }),
    });
    if (!res.ok) throw await toError(res);

    const type = res.headers.get("content-type") || "";
    if (!res.body || !type.includes("text/event-stream")) {
      const reply = (await res.json()) as BotReply;
      handlers.onDelta(reply.text);
      return reply;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let done: BotReply | null = null;

    for (;;) {
      const { value, done: finished } = await reader.read();
      if (value) buffer += decoder.decode(value, { stream: true });
      buffer = buffer.replace(/\r\n/g, "\n");
      let cut: number;
      while ((cut = buffer.indexOf("\n\n")) !== -1) {
        const event = parseEvent(buffer.slice(0, cut));
        buffer = buffer.slice(cut + 2);
        if (!event) continue;
        if (event.name === "delta") handlers.onDelta((event.data as { text: string }).text || "");
        else if (event.name === "status") handlers.onStatus?.((event.data as { text: string }).text || "");
        else if (event.name === "done") done = event.data as BotReply;
      }
      if (finished) break;
    }
    if (!done) throw new ApiError(0, "stream_incomplete", "The reply was cut off.");
    return done;
  }

  private async request<T>(method: string, path: string, body?: unknown, token?: string): Promise<T> {
    const headers: Record<string, string> = {};
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (token) headers["X-Conversation-Token"] = token;
    const res = await fetch(this.base + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!res.ok) throw await toError(res);
    if (res.status === 204) return undefined as T;
    return (await res.json()) as T;
  }
}

function parseEvent(block: string): { name: string; data: unknown } | null {
  let name = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  if (!data.length) return null;
  try {
    return { name, data: JSON.parse(data.join("\n")) };
  } catch {
    return null;
  }
}

async function toError(res: Response): Promise<ApiError> {
  let detail = res.statusText || "Request failed";
  let code = "http_error";
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    if (typeof body.code === "string") code = body.code;
  } catch {
    /* not JSON */
  }
  return new ApiError(res.status, code, detail);
}
