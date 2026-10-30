import { ApiError, type WidgetApi } from "./api";
import { renderMarkdown } from "./markdown";
import { loadChat, newLocalId, saveChat, visitorId, type SavedChat } from "./storage";
import css from "./styles.css?inline";
import type { Appearance, BotReply, ChatMessage, ChatStatus, Citation, HelpArticleSummary, LiveUpdates, Score, WidgetConfig } from "./types";

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
  book: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM4 19V5M8 7h7",
  back: "M15 6l-6 6 6 6",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  external: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6",
  minimize: "M9 4v5H4M15 20v-5h5M4 9l5-5M20 15l-5 5",
  sad: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8 16.5c1-1.3 2.4-2 4-2s3 .7 4 2M9 10h.01M15 10h.01",
  neutral: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8.5 15h7M9 10h.01M15 10h.01",
  happy: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8 14c1 1.4 2.4 2.2 4 2.2s3-.8 4-2.2M9 10h.01M15 10h.01",
} as const;
type IconName = keyof typeof ICONS;

const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
const FEEDBACK_OUTCOMES = new Set(["answered", "partial", "fallback"]);
const LIVE: ChatStatus[] = ["waiting", "human"];
// How often to check for agent messages. Fast while a person is on the chat
// and the panel is open; slow otherwise, in case an agent jumps in.
const POLL_MS = { liveOpen: 3000, liveClosed: 15000, botOpen: 15000, botClosed: 60000 };
const IDLE_STOP_MS = 30 * 60 * 1000;
// "Did this help?" appears under a resolved answer after the visitor goes quiet.
const ASK_RATING_MS = 60 * 1000;
const FACES: { score: Score; icon: IconName; label: string }[] = [
  { score: 1, icon: "sad", label: "Unhappy" },
  { score: 2, icon: "neutral", label: "Okay" },
  { score: 3, icon: "happy", label: "Happy" },
];
const FONTS: Record<string, string> = {
  rounded: 'ui-rounded, "SF Pro Rounded", "Nunito", "Varela Round", system-ui, sans-serif',
  serif: 'ui-serif, Georgia, Cambria, "Times New Roman", serif',
  mono: 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace',
};

/** A second gradient colour when the owner didn't pick one: the accent, hue-shifted. */
function shiftHue(hex: string, degrees: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!m) return "#EC4899";
  const n = parseInt(m[1], 16);
  let r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h = 0;
  const l = (max + min) / 2;
  const d = max - min;
  const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  if (d) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
  }
  h = (h * 60 + degrees + 360) % 360;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const o = l - c / 2;
  [r, g, b] = h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x] : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x];
  return "#" + [r, g, b].map((v) => Math.round((v + o) * 255).toString(16).padStart(2, "0")).join("");
}

/** Root classes and variables for the widget's design options. */
export function designClasses(a: Appearance): string {
  return [
    `layout-${a.layout || "classic"}`,
    `header-${a.header_style || "solid"}`,
    `corner-${a.corner || "rounded"}`,
    `bubble-${a.bubble || "filled"}`,
    `size-${a.size || "standard"}`,
  ].join(" ");
}

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
  private rated: number | null = null;
  private askedInline = false;
  private askTimer: number | undefined;
  private panel!: HTMLDivElement;
  private endBtn!: HTMLButtonElement;
  private sheet: HTMLElement | null = null;
  private helpView: HTMLElement | null = null;
  private articleView: HTMLElement | null = null;
  private ratedArticles = new Map<string, boolean>();

  constructor(
    private readonly api: WidgetApi,
    private readonly botId: string,
    private readonly config: WidgetConfig,
  ) {
    const a = config.appearance;
    this.host = el("div", { id: "pingie-widget", "data-pingie-version": __PINGIE_VERSION__ });
    const shadow = this.host.attachShadow({ mode: "open" });
    shadow.appendChild(el("style", {}, css));

    this.root = el("div", {
      class: `root ${a.theme === "light" ? "light" : "dark"} ${a.position === "left" ? "left" : "right"} ${designClasses(a)}`,
    });
    this.root.style.setProperty("--accent", a.accent || "#7C3AED");
    this.root.style.setProperty("--accent-2", a.accent_2 || shiftHue(a.accent || "#7C3AED", 40));
    if (a.font && FONTS[a.font]) this.root.style.setProperty("--font", FONTS[a.font]);
    shadow.appendChild(this.root);

    const saved = loadChat(botId);
    if (saved) {
      this.chat = { conversationId: saved.conversationId, token: saved.token };
      this.messages = saved.messages;
      this.status = saved.status ?? "bot";
      this.agentName = saved.agentName ?? null;
      this.lastLiveAt = saved.lastLiveAt;
      this.lastActivity = saved.savedAt;
      this.rated = saved.rated ?? null;
      this.askedInline = !!saved.askedInline;
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
    this.launcher.replaceChildren(this.launcherIcon());
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
    this.rated = null;
    this.askedInline = false;
    window.clearTimeout(this.pollTimer);
    window.clearTimeout(this.askTimer);
    this.closeSheet();
    this.renderStatus();
    saveChat(this.botId, null);
    this.renderMessages();
    this.input.focus();
  }

  destroy(): void {
    window.clearTimeout(this.pollTimer);
    window.clearTimeout(this.askTimer);
    this.host.remove();
  }

  // --- layout ---------------------------------------------------------------

  private build(): void {
    const a = this.config.appearance;
    const title = a.title || this.config.name || "Assistant";

    this.statusEl = el("span", { class: "status" });
    const helpBtn = el("button", { type: "button", class: "icon-btn", "aria-label": "Help articles", title: "Help articles" }, icon("book", 16));
    helpBtn.addEventListener("click", () => void this.openHelp());
    this.endBtn = el("button", { type: "button", class: "end-btn", title: "End this chat" }, "End");
    this.endBtn.addEventListener("click", () => this.openSurvey("end"));
    const resetBtn = el("button", { type: "button", class: "icon-btn", "aria-label": "Start a new conversation", title: "New conversation" }, icon("refresh", 16));
    resetBtn.addEventListener("click", () => this.reset());
    const closeBtn = el("button", { type: "button", class: "icon-btn", "aria-label": "Close chat" }, icon("close", 16));
    closeBtn.addEventListener("click", () => this.close());

    const head = el(
      "div",
      { class: "head" },
      this.avatar(17),
      el("span", { class: "title" }, el("strong", {}, title), this.statusEl),
      ...(this.config.help_center ? [helpBtn] : []),
      this.endBtn,
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

    this.panel = el("div", { class: "panel", role: "dialog", "aria-label": title }, head, this.body, composer);
    if (a.show_branding) {
      this.panel.appendChild(
        el("div", { class: "brand" }, "Powered by ", el("a", { href: "https://pingie.app", target: "_blank", rel: "noopener noreferrer" }, "Pingie")),
      );
    }
    this.panel.addEventListener("keydown", (e) => {
      if (e.key !== "Escape") return;
      // Close the topmost layer first: survey, article, help list, then the panel.
      if (this.sheet) this.closeSheet();
      else if (this.articleView) this.closeArticle();
      else if (this.helpView) this.closeHelp();
      else {
        this.close();
        this.launcher.focus();
      }
    });

    this.launcher = el("button", { type: "button", class: "launcher", "aria-label": "Open chat", "aria-expanded": "false" });
    this.launcher.appendChild(this.launcherIcon());
    this.launcher.addEventListener("click", () => this.toggle());

    this.root.append(this.panel, this.launcher);
  }

  /** The owner's logo when set (paid plans), else the chosen icon. */
  private avatar(size: number): HTMLElement {
    const a = this.config.appearance;
    const wrap = el("span", { class: "avatar" });
    const fallback = () => wrap.replaceChildren(icon(a.launcher in ICONS ? a.launcher : "chat", size));
    if (a.logo_url && /^https:\/\//i.test(a.logo_url)) {
      const img = el("img", { src: a.logo_url, alt: "" });
      img.addEventListener("error", fallback, { once: true });
      wrap.classList.add("logo");
      wrap.appendChild(img);
    } else {
      fallback();
    }
    return wrap;
  }

  private launcherIcon(): Node {
    const a = this.config.appearance;
    if (a.logo_url && /^https:\/\//i.test(a.logo_url)) {
      const img = el("img", { src: a.logo_url, alt: "", class: "launcher-logo" });
      img.addEventListener("error", () => img.replaceWith(icon(a.launcher in ICONS ? a.launcher : "chat", 24)), { once: true });
      return img;
    }
    return icon(a.launcher in ICONS ? a.launcher : "chat", 24);
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
    } else if (this.status === "closed") {
      text = "Chat ended · send a message to start again";
      cls = "status offline";
    }
    this.statusEl.className = cls;
    this.statusEl.title = text;
    this.statusEl.replaceChildren(el("span", { class: "status-text" }, text));
    // End only makes sense for a chat that has started and is still open.
    this.endBtn.hidden = !this.chat || this.status === "closed" || !this.messages.some((m) => m.role === "visitor");
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

    // The welcome layout opens on a hero (logo, name, soft gradient) until the
    // visitor says something, then becomes a normal chat.
    const hero = a.layout === "welcome" && !this.messages.some((m) => m.role === "visitor");
    this.root.classList.toggle("hero-on", hero);
    if (hero) {
      nodes.push(el("div", { class: "hero" }, this.avatar(28), el("strong", { class: "hero-title" }, a.title || this.config.name || "Assistant")));
    }
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
    const browse = isLast && this.config.help_center && (m.outcome === "fallback" || m.outcome === "partial");
    const human = m.offerHuman && isLast && this.status === "bot";
    if (browse || human) {
      const actions = el("div", { class: "actions" });
      if (browse) actions.appendChild(this.browseButton());
      if (human) actions.appendChild(this.humanButton());
      node.appendChild(actions);
    }
    if (m.askRating) node.appendChild(this.inlineRating(m));
    return node;
  }

  private browseButton(): HTMLElement {
    const btn = el("button", { type: "button", class: "human-btn" }, icon("book", 14), "Browse help articles");
    btn.addEventListener("click", () => void this.openHelp());
    return btn;
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
      if (c.article_id && this.config.help_center) {
        // Readable in the Help Center: open it here instead of a new tab.
        const btn = el("button", { type: "button", class: "source", title: `Read: ${label}` }, icon("book", 11), el("span", {}, label));
        const id = c.article_id;
        btn.addEventListener("click", () => void this.openArticle(id, false));
        wrap.appendChild(btn);
        continue;
      }
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
    window.clearTimeout(this.askTimer);

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
      if (done.outcome === "answered") this.scheduleAskRating(reply);
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

  // --- rating the chat ------------------------------------------------------

  private faceButtons(selected: number | null, onPick: (score: Score) => void, size = 26): HTMLElement {
    const row = el("div", { class: "faces", role: "radiogroup", "aria-label": "Rate this chat" });
    for (const f of FACES) {
      const btn = el(
        "button",
        { type: "button", class: "face", role: "radio", "aria-checked": String(selected === f.score), "aria-label": f.label, title: f.label },
        icon(f.icon, size),
      );
      btn.addEventListener("click", () => onPick(f.score));
      row.appendChild(btn);
    }
    return row;
  }

  /** "Did this help?" under a resolved answer, once the visitor has gone quiet. */
  private scheduleAskRating(m: ChatMessage): void {
    window.clearTimeout(this.askTimer);
    if (this.rated !== null || this.askedInline) return;
    this.askTimer = window.setTimeout(() => {
      const last = this.messages[this.messages.length - 1];
      if (last !== m || this.status !== "bot" || this.rated !== null || this.askedInline) return;
      m.askRating = true;
      this.askedInline = true;
      this.update(m);
      this.persist();
    }, ASK_RATING_MS);
  }

  private inlineRating(m: ChatMessage): HTMLElement {
    const wrap = el("div", { class: "ask-rating" });
    if (m.ratedScore) {
      wrap.textContent = "Thanks for the feedback!";
      return wrap;
    }
    wrap.append(
      el("span", {}, "Did this help?"),
      this.faceButtons(null, (score) => {
        m.ratedScore = score;
        this.update(m);
        void this.sendRating(score, "", "inline");
      }, 18),
    );
    return wrap;
  }

  private async sendRating(score: Score, comment: string, source: "end" | "closed" | "inline"): Promise<boolean> {
    if (!this.chat) return false;
    try {
      await this.api.rate(this.chat.conversationId, this.chat.token, score, comment, source);
      this.rated = score;
      this.persist();
      return true;
    } catch {
      return false;
    }
  }

  /** The survey sheet: after the visitor clicks End, or when a person ended the chat. */
  private openSurvey(mode: "end" | "closed"): void {
    if (this.sheet) return;
    const a = this.config.appearance;
    let score: Score | null = this.rated && this.rated > 0 ? (this.rated as Score) : null;

    const comment = el("textarea", { class: "sheet-comment", rows: "2", maxlength: "500", placeholder: "Tell us more (optional)", "aria-label": "Comment" });
    comment.hidden = score === null;
    const submit = el("button", { type: "button", class: "sheet-primary" }, mode === "end" ? "Submit and end chat" : "Submit");
    submit.disabled = score === null;
    const cancel = el("button", { type: "button", class: "sheet-link" }, mode === "end" ? "Cancel" : "Skip");
    const error = el("p", { class: "sheet-error", role: "alert" });

    let faces: HTMLElement;
    const pick = (s: Score) => {
      score = s;
      const next = this.faceButtons(score, pick);
      faces.replaceWith(next);
      faces = next;
      comment.hidden = false;
      submit.disabled = false;
    };
    faces = this.faceButtons(score, pick);

    const card = el(
      "div",
      { class: "sheet-card", role: "dialog", "aria-modal": "true", "aria-label": "Rate this chat" },
      el("p", { class: "sheet-title" }, `How was your chat with ${a.title || this.config.name || "us"}?`),
      faces,
      comment,
      error,
      submit,
      cancel,
    );
    cancel.addEventListener("click", () => this.closeSheet());
    submit.addEventListener("click", async () => {
      if (score === null) return;
      submit.disabled = true;
      error.textContent = "";
      const ok = await this.sendRating(score, comment.value.trim(), mode);
      if (!ok) {
        error.textContent = "Couldn't send your rating. Please try again.";
        submit.disabled = false;
        return;
      }
      if (mode === "end") await this.endChat();
      card.replaceChildren(el("p", { class: "sheet-title" }, "Thanks for your feedback!"), el("p", { class: "sheet-sub" }, "It helps us get better."));
      window.setTimeout(() => this.closeSheet(), 1600);
    });

    this.sheet = el("div", { class: "sheet" }, card);
    this.panel.appendChild(this.sheet);
    const first = card.querySelector<HTMLButtonElement>(".face");
    first?.focus();
  }

  private closeSheet(): void {
    this.sheet?.remove();
    this.sheet = null;
  }

  private async endChat(): Promise<void> {
    if (!this.chat) return;
    try {
      await this.api.end(this.chat.conversationId, this.chat.token);
      this.status = "closed";
      window.clearTimeout(this.askTimer);
      this.renderStatus();
      await this.poll(); // picks up "This chat has ended…"
    } catch {
      /* the rating is saved; the chat simply stays open */
    }
  }

  // --- Help Center -----------------------------------------------------------

  private layer(cls: string, title: string, onBack: () => void, ...actions: HTMLElement[]): { view: HTMLElement; content: HTMLElement } {
    const back = el("button", { type: "button", class: "icon-btn", "aria-label": "Back" }, icon("back", 18));
    back.addEventListener("click", onBack);
    const content = el("div", { class: "layer-body" });
    const view = el(
      "div",
      { class: `layer ${cls}`, role: "region", "aria-label": title },
      el("div", { class: "head layer-head" }, back, el("span", { class: "title" }, el("strong", {}, title)), ...actions),
      content,
    );
    return { view, content };
  }

  private async openHelp(): Promise<void> {
    if (this.helpView) return;
    const { view, content } = this.layer("help", "Help Center", () => this.closeHelp());
    const list = el("div", { class: "articles", "aria-live": "polite" });
    const search = el("input", { type: "search", class: "help-search", placeholder: "What can we help you with?", "aria-label": "Search help articles" });
    const bar = el("div", { class: "help-bar" }, search, el("span", { class: "help-search-icon" }, icon("search", 16)));
    content.append(list);
    view.appendChild(bar);
    this.helpView = view;
    this.panel.appendChild(view);

    let seq = 0;
    const load = async (q: string) => {
      const mine = ++seq;
      list.replaceChildren(el("p", { class: "help-empty" }, "Loading…"));
      try {
        const items = await this.api.help(q);
        if (mine !== seq) return;
        this.renderArticles(list, items, q);
      } catch {
        if (mine === seq) list.replaceChildren(el("p", { class: "help-empty" }, "Couldn't load articles. Please try again."));
      }
    };
    let timer: number | undefined;
    search.addEventListener("input", () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => void load(search.value.trim()), 300);
    });
    await load("");
    search.focus();
  }

  private renderArticles(list: HTMLElement, items: HelpArticleSummary[], q: string): void {
    if (!items.length) {
      list.replaceChildren(el("p", { class: "help-empty" }, q ? `No articles match “${q}”. Try other words, or ask the assistant.` : "No articles yet."));
      return;
    }
    list.replaceChildren(
      ...items.map((item) => {
        const card = el("button", { type: "button", class: "article-card" }, el("strong", {}, item.title), el("span", {}, item.snippet));
        card.addEventListener("click", () => void this.openArticle(item.id, true));
        return card;
      }),
    );
  }

  private closeHelp(): void {
    this.closeArticle();
    this.helpView?.remove();
    this.helpView = null;
    this.input.focus();
  }

  private async openArticle(id: string, fromList: boolean): Promise<void> {
    this.closeArticle();
    const close = el("button", { type: "button", class: "icon-btn", "aria-label": "Back to chat", title: "Back to chat" }, icon("close", 16));
    close.addEventListener("click", () => {
      this.closeArticle();
      this.closeHelp();
    });
    const { view, content } = this.layer("article", fromList ? "Help Center" : "Article", () => this.closeArticle(), close);
    content.appendChild(el("p", { class: "help-empty" }, "Loading…"));
    this.articleView = view;
    this.panel.appendChild(view);
    try {
      const article = await this.api.article(id);
      if (this.articleView !== view) return;
      const body = el("div", { class: "article-text" });
      body.innerHTML = renderMarkdown(article.body, true); // escaped by renderMarkdown
      const nodes: Node[] = [el("h1", { class: "article-title" }, article.title), body];
      if (article.url && isUrl(article.url)) {
        nodes.push(el("a", { class: "article-link", href: article.url, target: "_blank", rel: "noopener noreferrer" }, "Open the original page", icon("external", 12)));
      }
      content.replaceChildren(...nodes);
      view.appendChild(this.articleFeedback(id, article.title));
    } catch {
      content.replaceChildren(el("p", { class: "help-empty" }, "This article isn't available any more."));
    }
  }

  private articleFeedback(id: string, title: string): HTMLElement {
    const bar = el("div", { class: "article-feedback" });
    const render = () => {
      const done = this.ratedArticles.get(id);
      if (done === true) {
        bar.replaceChildren(el("span", {}, "Glad it helped!"));
        return;
      }
      if (done === false) {
        const ask = el("button", { type: "button", class: "human-btn" }, "Ask the assistant");
        ask.addEventListener("click", () => {
          this.closeHelp();
          this.input.value = `About “${title}”: `;
          this.autosize();
          this.input.focus();
        });
        const extra: HTMLElement[] = [ask];
        if (this.config.agents_online && this.status === "bot") {
          const human = this.humanButton();
          human.addEventListener("click", () => this.closeHelp());
          extra.push(human);
        }
        bar.replaceChildren(el("span", {}, "Sorry about that. Still need help?"), el("div", { class: "actions" }, ...extra));
        return;
      }
      const yes = el("button", { type: "button", class: "face", "aria-label": "Yes", title: "Yes" }, icon("happy", 20));
      const no = el("button", { type: "button", class: "face", "aria-label": "No", title: "No" }, icon("sad", 20));
      yes.addEventListener("click", () => void vote(true));
      no.addEventListener("click", () => void vote(false));
      bar.replaceChildren(el("span", {}, "Did this answer your question?"), el("div", { class: "faces" }, yes, no));
    };
    const vote = async (helpful: boolean) => {
      this.ratedArticles.set(id, helpful);
      render();
      try {
        await this.api.articleFeedback(id, helpful);
      } catch {
        /* a lost vote isn't worth bothering the visitor about */
      }
    };
    render();
    return bar;
  }

  private closeArticle(): void {
    this.articleView?.remove();
    this.articleView = null;
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
    const justClosed = u.status === "closed" && this.status !== "closed";
    if (u.rated && this.rated === null) this.rated = 0; // rated elsewhere; don't ask again
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
    // A person ended the chat: ask how it went (once).
    if (justClosed && this.rated === null && !this.sheet) this.openSurvey("closed");
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
      rated: this.rated ?? undefined,
      askedInline: this.askedInline,
    };
    saveChat(this.botId, saved);
  }
}
