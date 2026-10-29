// Entry point of widget.js. Customers embed:
//
//   <script src="https://cdn.pingie.app/widget.js" data-bot-id="bot_xxx" defer></script>
//
// Optional attributes: data-api="https://api.example.com" sets the backend
// (default: VITE_API_BASE from the build, else the script's own origin);
// data-open="true" opens the chat on load.
//
// The script must never break the host page: every failure is caught and,
// at most, logged once as a console warning.

import { ApiError, WidgetApi } from "./api";
import { Widget, type Identity } from "./ui";

interface PingieApi {
  version: string;
  open(): void;
  close(): void;
  toggle(): void;
  identify(identity: Identity): void;
  ask(text: string): void;
  reset(): void;
  destroy(): void;
}

declare global {
  interface Window {
    Pingie?: PingieApi;
  }
}

/** data-api, else the backend baked in at build time, else the origin the
 * script was loaded from (when ping-backend itself serves /widget.js). */
function apiBase(script: HTMLScriptElement): string {
  const explicit = script.dataset.api?.trim() || import.meta.env.VITE_API_BASE;
  if (explicit) return explicit;
  try {
    return new URL(script.src, location.href).origin;
  } catch {
    return location.origin;
  }
}

function findScript(): HTMLScriptElement | null {
  const current = document.currentScript;
  if (current instanceof HTMLScriptElement && current.dataset.botId) return current;
  // currentScript is null for deferred/async-injected module scripts.
  return document.querySelector<HTMLScriptElement>("script[data-bot-id]");
}

function whenReady(fn: () => void): void {
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn, { once: true });
  else fn();
}

function boot(): void {
  if (window.Pingie) return; // the snippet was pasted twice

  const script = findScript();
  const botId = script?.dataset.botId?.trim();
  if (!script || !botId) {
    console.warn("[Pingie] Missing data-bot-id on the widget script tag.");
    return;
  }
  const openOnLoad = script.dataset.open === "true";

  // Calls made before the config arrives are replayed once the widget exists.
  const queue: ((w: Widget) => void)[] = [];
  let widget: Widget | null = null;
  const call = (fn: (w: Widget) => void) => (widget ? fn(widget) : queue.push(fn));

  window.Pingie = {
    version: __PINGIE_VERSION__,
    open: () => call((w) => w.open()),
    close: () => call((w) => w.close()),
    toggle: () => call((w) => w.toggle()),
    identify: (identity) => call((w) => w.identify(identity || {})),
    ask: (text) => call((w) => w.ask(String(text ?? ""))),
    reset: () => call((w) => w.reset()),
    destroy: () => {
      widget?.destroy();
      widget = null;
      delete window.Pingie;
    },
  };

  const api = new WidgetApi(apiBase(script), botId);
  api
    .config()
    .then((config) => {
      whenReady(() => {
        if (!window.Pingie) return; // destroyed while loading
        widget = new Widget(api, botId, config);
        if (openOnLoad) widget.open(false);
        for (const fn of queue.splice(0)) fn(widget);
      });
    })
    .catch((err) => {
      // Not allowed on this domain, unknown bot, draft bot on a live site,
      // or the backend is unreachable: stay invisible, explain in the console.
      const why = err instanceof ApiError ? `${err.message} (HTTP ${err.status})` : "could not reach the Pingie API";
      console.warn(`[Pingie] Widget not loaded for bot "${botId}": ${why}`);
      delete window.Pingie;
    });
}

try {
  boot();
} catch (err) {
  console.warn("[Pingie] Widget failed to start:", err);
}
