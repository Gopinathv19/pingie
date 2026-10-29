import { ApiError, type WidgetApi } from "./api";
import { renderMarkdown } from "./markdown";
import { loadChat, newLocalId, saveChat, visitorId, type SavedChat } from "./storage";
import css from "./styles.css?inline";
import type { BotReply, ChatMessage, ChatStatus, Citation, LiveUpdates, WidgetConfig } from "./types";

// Same stroke icons as the dashboard (ping-frontend/src/components/Icon.tsx).
const ICONS = {
  chat: "M4 4h16v12H9l-5 4z",
  spark: "M12 3v6M12 15v6M3 12h6M15 12h6M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3",
  help: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.7v.5M12 17v.5",
  close: "M6 6l12 12M18 6L6 18",
  send: "M4 12l16-8-6 16-3-7z",
  file: "M6 3h9l4 4v14H6zM14 3v5h5",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  refresh: "M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7",
  thumbUp: "M7 11v9H4v-9zM7 11l4-8c1.5 0 2.5 1 2.5 2.5V9h5.5l-2 11H7",
  thumbDown: "M7 13V4H4v9zM7 13l4 8c1.5 0 2.5-1 2.5-2.5V15h5.5l-2-11H7",
  chevronDown: "M6 9l6 6 6-6",
  person: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c0-4 3.6-6 8-6s8 2 8 6",
} as const;
type IconName = keyof typeof ICONS;

const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
const FEEDBACK_OUTCOMES = new Set(["answered", "partial", "fallback"]);
const LIVE: ChatStatus[] = ["waiting", "human"];
// How often to check for agent messages. Fast while a person is on the chat
// and the panel is open; slow otherwise, in case an agent jumps in.
const POLL_MS = { liveOpen: 3000, liveClosed: 15000, botOpen: 15000, botClosed: 60000 };
const IDLE_STOP_MS = 30 * 60 * 1000;

function icon(name: IconName, size = 18): SVGSVGElement {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.8");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  const path = document.createElementNS(NS, "path");
  path.setAttribute("d", ICONS[name]);
  svg.appendChild(path);
  return svg;
}

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Record<string, string> = {},
  ...children: (Node | string)[]
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c);
  return node;
}

function isUrl(s: string | undefined): s is string {
  return !!s && /^https?:\/\//i.test(s);
}

export interface Identity {
  email?: string;
  name?: string;
}

export class Widget {
  private readonly host: HTMLElement;
  private readonly root: HTMLDivElement;
  private body!: HTMLDivElement;
  private input!: HTMLTextAreaElement;
  private sendBtn!: HTMLButtonElement;
  private launcher!: HTMLButtonElement;
  private statusEl!: HTMLSpanElement;

  private messages: ChatMessage[] = [];
  private chat: { conversationId: string; token: string } | null = null;
  private starting: Promise<{ conversationId: string; token: string }> | null = null;
  private identity: Identity | null = null;
  private isOpen = false;
  private busy = false;
  private status: ChatStatus = "bot";
  private agentName: string | null = null;
  private lastLiveAt: string | undefined;
  private lastActivity = Date.now();
  private pollTimer: number | undefined;
  private unseen = false;

  constructor(
    private readonly api: WidgetApi,
    private readonly botId: string,
    private readonly config: WidgetConfig,
  ) {
    const a = config.appearance;
    this.host = el("div", { id: "pingie-widget", "data-pingie-version": __PINGIE_VERSION__ });
    const shadow = this.host.attachShadow({ mode: "open" });
    shadow.appendChild(el("style", {}, css));

    this.root = el("div", { class: `root ${a.theme === "light" ? "light" : "dark"} ${a.position === "left" ? "left" : "right"}` });
    this.root.style.setProperty("--accent", a.accent || "#7C3AED");
    shadow.appendChild(this.root);

    const saved = loadChat(botId);
    if (saved) {
      this.chat = { conversationId: saved.conversationId, token: saved.token };
      this.messages = saved.messages;
      this.status = saved.status ?? "bot";
      this.agentName = saved.agentName ?? null;
      this.lastLiveAt = saved.lastLiveAt;
      this.lastActivity = saved.savedAt;
    }

    this.build();
    this.renderMessages();
    this.renderStatus();
    document.body.appendChild(this.host);
    if (saved?.open) this.open(false);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) this.schedulePoll(0);
    });
    if (this.chat) this.schedulePoll(LIVE.includes(this.status) ? 0 : undefined);
  }

  // --- public API (window.Pingie) ------------------------------------------

  open(focus = true): void {
    this.isOpen = true;
    this.root.classList.add("open");
    this.launcher.setAttribute("aria-expanded", "true");
    this.launcher.setAttribute("aria-label", "Close chat");
    this.launcher.replaceChildren(icon("chevronDown", 24));
    this.launcher.classList.remove("unseen");
    this.unseen = false;
    this.scrollToEnd();
    this.schedulePoll(LIVE.includes(this.status) ? 0 : undefined);
    if (focus) setTimeout(() => this.input.focus(), 60);
    this.persist();
  }

  close(): void {
    this.isOpen = false;
    this.root.classList.remove("open");
    this.launcher.setAttribute("aria-expanded", "false");
    this.launcher.setAttribute("aria-label", "Open chat");
    this.launcher.replaceChildren(icon(this.config.appearance.launcher in ICONS ? this.config.appearance.launcher : "chat", 24));
    this.persist();
  }

  toggle(): void {
    if (this.isOpen) this.close();
    else this.open();
  }

  /** Attribute the chat to a signed-in user. Safe to call before the visitor
   * has said anything: it is applied when the conversation starts. */
  identify(identity: Identity): void {
    const email = identity.email?.trim() || undefined;
    const name = identity.name?.trim() || undefined;
    if (email && !EMAIL_RE.test(email)) {
      console.warn("[Pingie] identify(): ignoring an invalid email");
      return;
    }
    this.identity = { email, name };
    if (this.chat) void this.sendIdentity(this.chat);
  }

  /** Open the widget and ask a question as the visitor. */
  ask(text: string): void {
    this.open();
    void this.send(text);
  }

  /** Forget this conversation and start a new one. */
  reset(): void {
    if (this.busy) return;
    this.chat = null;
    this.messages = [];
    this.status = "bot";
    this.agentName = null;
    this.lastLiveAt = undefined;
    window.clearTimeout(this.pollTimer);
    this.renderStatus();
    saveChat(this.botId, null);
    this.renderMessages();
    this.input.focus();
  }

  destroy(): void {
    window.clearTimeout(this.pollTimer);
    this.host.remove();
  }

  // --- layout ---------------------------------------------------------------

  private build(): void {
    const a = this.config.appearance;
    const title = a.title || this.config.name || "Assistant";

    this.statusEl = el("span", { class: "status" });
    const resetBtn = el("button", { type: "button", class: "icon-btn", "aria-label": "Start a new conversation", title: "New conversation" }, icon("refresh", 16));
    resetBtn.addEventListener("click", () => this.reset());
    const closeBtn = el("button", { type: "button", class: "icon-btn", "aria-label": "Close chat" }, icon("close", 16));
    closeBtn.addEventListener("click", () => this.close());

    const head = el(
      "div",
      { class: "head" },
      el("span", { class: "avatar" }, icon(a.launcher in ICONS ? a.launcher : "chat", 17)),
      el("span", { class: "title" }, el("strong", {}, title), this.statusEl),
      resetBtn,
      closeBtn,
    );

    this.body = el("div", { class: "body", role: "log", "aria-live": "polite", "aria-label": `${title} conversation` });

    this.input = el("textarea", { rows: "1", placeholder: a.placeholder || "Ask a question…", "aria-label": "Message", maxlength: "2000" });
    this.input.addEventListener("input", () => this.autosize());
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        this.submit();
      }
    });
    this.sendBtn = el("button", { type: "button", class: "send", "aria-label": "Send" }, icon("send", 16));
    this.sendBtn.addEventListener("click", () => this.submit());
    const composer = el("div", { class: "composer" }, this.input, this.sendBtn);

    const panel = el("div", { class: "panel", role: "dialog", "aria-label": title }, head, this.body, composer);
    if (a.show_branding) {
      panel.appendChild(
        el("div", { class: "brand" }, "Powered by ", el("a", { href: "https://pingie.app", target: "_blank", rel: "noopener noreferrer" }, "Pingie")),
      );
    }
    panel.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        this.close();
        this.launcher.focus();
      }
    });

    this.launcher = el("button", { type: "button", class: "launcher", "aria-label": "Open chat", "aria-expanded": "false" });
    this.launcher.appendChild(icon(a.launcher in ICONS ? a.launcher : "chat", 24));
    this.launcher.addEventListener("click", () => this.toggle());

    this.root.append(panel, this.launcher);
  }

  private renderStatus(): void {
    let text = this.config.online ? "Typically replies instantly" : "Offline";
    let cls = this.config.online ? "status" : "status offline";
    if (this.status === "waiting") {
      text = "Connecting you to a person…";
      cls = "status waiting";
    } else if (this.status === "human") {
      text = this.agentName ? `${this.agentName} from the team` : "Chatting with the team";
      cls = "status human";
    }
    this.statusEl.className = cls;
    this.statusEl.textContent = text;
  }

  private autosize(): void {
    this.input.style.height = "auto";
    this.input.style.height = `${Math.min(this.input.scrollHeight, 120)}px`;
  }

  private setBusy(busy: boolean): void {
    this.busy = busy;
    this.sendBtn.disabled = busy;
  }

  private scrollToEnd(): void {
    requestAnimationFrame(() => {
      this.body.scrollTop = this.body.scrollHeight;
    });
  }

  // --- rendering ------------------------------------------------------------

  private renderMessages(): void {
    const a = this.config.appearance;
    const nodes: Node[] = [];

    if (a.welcome) nodes.push(this.bubble({ id: "welcome", role: "bot", text: a.welcome }));

    const suggestions = a.suggestions.filter(Boolean);
    if (suggestions.length && !this.messages.some((m) => m.role === "visitor")) {
      const chips = el("div", { class: "chips" });
      for (const q of suggestions) {
        const chip = el("button", { type: "button", class: "chip" }, q);
        chip.addEventListener("click", () => void this.send(q));
        chips.appendChild(chip);
      }
      nodes.push(chips);
    }

    const last = this.messages[this.messages.length - 1];
    for (const m of this.messages) nodes.push(this.bubble(m, m === last));

    this.body.replaceChildren(...nodes);
    this.scrollToEnd();
  }

  private bubble(m: ChatMessage, isLast = false): HTMLElement {
    const node = el("div", { class: `msg ${m.role}${m.error ? " error" : ""}`, "data-id": m.id });

    if (m.role === "visitor" || m.error) {
      node.textContent = m.text;
      return node;
    }
    if (m.role === "system") {
      node.textContent = m.text;
      if (m.asksForEmail && isLast && !this.identity?.email) node.appendChild(this.emailForm());
      return node;
    }
    if (m.role === "agent") {
      node.append(el("span", { class: "author" }, `${m.authorName || "Team"} · Team`), el("div", { class: "agent-text" }, m.text));
      return node;
    }

    if (m.pending && !m.text) {
      node.appendChild(el("span", { class: "typing", "aria-label": "Typing" }, el("span"), el("span"), el("span")));
      if (m.statusText) node.appendChild(el("span", { class: "typing-status" }, m.statusText));
      return node;
    }

    const content = el("div");
    content.innerHTML = renderMarkdown(m.text); // escaped by renderMarkdown
    node.appendChild(content);
    if (m.pending) return node;

    if (this.config.appearance.show_sources && m.citations?.length) node.appendChild(this.sources(m.citations));
    if (m.messageId && m.outcome && FEEDBACK_OUTCOMES.has(m.outcome)) node.appendChild(this.feedback(m));
    if (m.asksForEmail && isLast && !this.identity?.email) node.appendChild(this.emailForm());
    if (m.offerHuman && isLast && this.status === "bot") node.appendChild(this.humanButton());
    return node;
  }

  private humanButton(): HTMLElement {
    const btn = el("button", { type: "button", class: "human-btn" }, icon("person", 14), "Talk to a person");
    btn.addEventListener("click", () => void this.requestHuman(btn));
    return btn;
  }

  private async requestHuman(btn: HTMLButtonElement): Promise<void> {
    btn.disabled = true;
    try {
      const chat = await this.conversation();
      const { status } = await this.api.handoff(chat.conversationId, chat.token);
      for (const m of this.messages) m.offerHuman = false;
      if (status !== "unavailable") this.status = status;
      this.renderStatus();
      await this.poll();
    } catch {
      btn.disabled = false;
    }
  }

  private sources(citations: Citation[]): HTMLElement {
    const wrap = el("div", { class: "sources" });
    const seen = new Set<string>();
    for (const c of citations) {
      const key = c.source_name || c.location || "";
      if (!key || seen.has(key)) continue;
      seen.add(key);
      const url = isUrl(c.location) ? c.location : isUrl(c.source_name) ? c.source_name : null;
      const label = url && c.source_name === url ? url.replace(/^https?:\/\/(www\.)?/, "").replace(/\/$/, "") : c.source_name;
      const chip = url
        ? el("a", { class: "source", href: url, target: "_blank", rel: "noopener noreferrer", title: url }, icon("link", 11), el("span", {}, label))
        : el("span", { class: "source", title: c.source_name }, icon("file", 11), el("span", {}, label));
      wrap.appendChild(chip);
    }
    return wrap;
  }

  private feedback(m: ChatMessage): HTMLElement {
    const wrap = el("div", { class: "feedback" });
    for (const [value, name, label] of [
      ["up", "thumbUp", "Helpful"],
      ["down", "thumbDown", "Not helpful"],
    ] as const) {
      const btn = el("button", { type: "button", "aria-label": label, title: label, "aria-pressed": String(m.feedback === value) }, icon(name, 14));
      btn.addEventListener("click", () => void this.rate(m, value));
      wrap.appendChild(btn);
    }
    return wrap;
  }

  private emailForm(): HTMLElement {
    const input = el("input", { type: "email", placeholder: "you@example.com", "aria-label": "Your email", autocomplete: "email" });
    const form = el("form", { class: "email-form" }, input, el("button", { type: "submit" }, "Send"));
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      const email = input.value.trim();
      if (!EMAIL_RE.test(email)) {
        input.setCustomValidity("Please enter a valid email");
        input.reportValidity();
        return;
      }
      // The backend is waiting for this conversation's next message to be the email.
      void this.send(email);
    });
    input.addEventListener("input", () => input.setCustomValidity(""));
    return form;
  }

  /** Re-render one message in place (cheap enough for every streamed delta). */
  private update(m: ChatMessage): void {
    const node = this.body.querySelector(`[data-id="${m.id}"]`);
    const isLast = m === this.messages[this.messages.length - 1];
    if (node) node.replaceWith(this.bubble(m, isLast));
    else this.renderMessages();
    const nearEnd = this.body.scrollHeight - this.body.scrollTop - this.body.clientHeight < 120;
    if (nearEnd) this.scrollToEnd();
  }

  // --- conversation ---------------------------------------------------------

  private submit(): void {
    const text = this.input.value.trim();
    if (!text || this.busy) return;
    this.input.value = "";
    this.autosize();
    void this.send(text);
  }

  private async send(raw: string): Promise<void> {
    const text = raw.trim().slice(0, 2000);
    if (!text || this.busy) return;
    this.setBusy(true);

    this.messages = this.messages.filter((m) => !m.error);
    this.messages.push({ id: newLocalId(), role: "visitor", text });
    const reply: ChatMessage = { id: newLocalId(), role: "bot", text: "", pending: true };
    this.messages.push(reply);
    this.renderMessages();

    try {
      await this.deliver(text, reply, true);
    } catch (err) {
      this.fail(reply, err);
    } finally {
      this.setBusy(false);
      this.persist();
    }
  }

  private async deliver(text: string, reply: ChatMessage, mayRetry: boolean): Promise<void> {
    const chat = await this.conversation();
    try {
      const done: BotReply = await this.api.send(chat.conversationId, chat.token, text, {
        onDelta: (delta) => {
          reply.text += delta;
          this.update(reply);
        },
        onStatus: (status) => {
          if (reply.text) return;
          reply.statusText = status;
          this.update(reply);
        },
      });
      this.lastActivity = Date.now();
      if (done.status) this.status = done.status;
      if (done.outcome === "human") {
        // A person is handling the chat; their reply arrives by polling.
        this.messages = this.messages.filter((m) => m !== reply);
      } else {
        Object.assign(reply, {
          text: done.text || reply.text,
          messageId: done.message_id ?? undefined,
          outcome: done.outcome,
          citations: done.citations || [],
          asksForEmail: !!done.asks_for_email,
          offerHuman: !!done.offer_human,
          pending: false,
          statusText: undefined,
        });
      }
      this.renderStatus();
      this.renderMessages();
      this.schedulePoll();
    } catch (err) {
      // An expired or unknown conversation: start a new one and try once more.
      const stale = err instanceof ApiError && (err.status === 401 || err.status === 404);
      if (stale && mayRetry && !reply.text) {
        this.chat = null;
        return this.deliver(text, reply, false);
      }
      throw err;
    }
  }

  private conversation(): Promise<{ conversationId: string; token: string }> {
    if (this.chat) return Promise.resolve(this.chat);
    if (!this.starting) {
      this.starting = this.api
        .start(visitorId(), location.href)
        .then((r) => {
          this.chat = { conversationId: r.conversation_id, token: r.token };
          if (this.identity) void this.sendIdentity(this.chat);
          return this.chat;
        })
        .finally(() => {
          this.starting = null;
        });
    }
    return this.starting;
  }

  private async sendIdentity(chat: { conversationId: string; token: string }): Promise<void> {
    if (!this.identity) return;
    try {
      await this.api.identify(chat.conversationId, chat.token, this.identity.email, this.identity.name);
    } catch (err) {
      console.warn("[Pingie] identify failed:", err instanceof Error ? err.message : err);
    }
  }

  private async rate(m: ChatMessage, value: "up" | "down"): Promise<void> {
    if (!this.chat || !m.messageId || m.feedback === value) return;
    const previous = m.feedback;
    m.feedback = value;
    this.update(m);
    try {
      await this.api.feedback(this.chat.conversationId, this.chat.token, m.messageId, value);
      this.persist();
    } catch {
      m.feedback = previous;
      this.update(m);
    }
  }

  private fail(reply: ChatMessage, err: unknown): void {
    let notice = "Sorry, something went wrong. Please try again.";
    if (err instanceof ApiError) {
      if (err.status === 429) notice = err.message || "You're sending messages too quickly. Please wait a moment.";
      else if (err.status === 402) notice = "This assistant isn't available right now. Please try again later.";
      else if (err.status === 403) notice = err.message;
      else if (err.status === 0) notice = "The reply was interrupted. Please try again.";
    } else if (err instanceof TypeError) {
      notice = "Couldn't reach the assistant. Check your connection and try again.";
    }

    if (reply.text) {
      // Part of the answer already arrived: keep it, then explain.
      reply.pending = false;
    } else {
      this.messages = this.messages.filter((m) => m !== reply);
    }
    this.messages.push({ id: newLocalId(), role: "bot", text: notice, error: true });
    this.renderMessages();
  }

  // --- live chat polling ----------------------------------------------------

  private schedulePoll(delay?: number): void {
    window.clearTimeout(this.pollTimer);
    if (!this.chat) return;
    const live = LIVE.includes(this.status);
    if (!live && Date.now() - this.lastActivity > IDLE_STOP_MS) return;
    const ms = delay ?? (live ? (this.isOpen ? POLL_MS.liveOpen : POLL_MS.liveClosed) : this.isOpen ? POLL_MS.botOpen : POLL_MS.botClosed);
    this.pollTimer = window.setTimeout(() => void this.poll(), ms);
  }

  private async poll(): Promise<void> {
    window.clearTimeout(this.pollTimer);
    if (!this.chat) return;
    if (document.hidden) return; // resumed by visibilitychange
    let updates: LiveUpdates;
    try {
      updates = await this.api.updates(this.chat.conversationId, this.chat.token, this.lastLiveAt);
    } catch (err) {
      if (err instanceof ApiError && (err.status === 401 || err.status === 404)) return;
      this.schedulePoll(POLL_MS.liveClosed);
      return;
    }
    this.applyUpdates(updates);
    this.schedulePoll();
  }

  private applyUpdates(u: LiveUpdates): void {
    const seen = new Set(this.messages.map((m) => m.messageId).filter(Boolean));
    let added = false;
    let fromAgent = false;
    for (const m of u.messages) {
      if (!this.lastLiveAt || m.created_at > this.lastLiveAt) this.lastLiveAt = m.created_at;
      if (seen.has(m.id)) continue;
      this.messages.push({
        id: newLocalId(),
        messageId: m.id,
        role: m.role,
        text: m.content,
        authorName: m.author_name ?? undefined,
        asksForEmail: m.asks_for_email,
      });
      added = true;
      if (m.role === "agent") fromAgent = true;
    }
    const changed = u.status !== this.status || (u.agent?.name ?? null) !== this.agentName;
    this.status = u.status;
    this.agentName = u.agent?.name ?? null;
    if (added) {
      this.lastActivity = Date.now();
      for (const m of this.messages) if (m.role === "bot") m.offerHuman = false;
      this.renderMessages();
      if (fromAgent && !this.isOpen && !this.unseen) {
        this.unseen = true;
        this.launcher.classList.add("unseen");
      }
    }
    if (changed) {
      this.renderStatus();
      if (!added) this.renderMessages();
    }
    if (added || changed) this.persist();
  }

  private persist(): void {
    if (!this.chat) return;
    const saved: SavedChat = {
      conversationId: this.chat.conversationId,
      token: this.chat.token,
      messages: this.messages,
      open: this.isOpen,
      savedAt: Date.now(),
      status: this.status,
      agentName: this.agentName ?? undefined,
      lastLiveAt: this.lastLiveAt,
    };
    saveChat(this.botId, saved);
  }
}
