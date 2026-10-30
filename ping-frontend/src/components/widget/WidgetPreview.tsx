"use client";

import { useState, type CSSProperties } from "react";
import { Icon, type IconName } from "@/components/Icon";
import type { WidgetAppearance } from "@/lib/types";
import s from "./widget.module.css";

export const launcherIcons: Record<WidgetAppearance["launcher"], IconName> = {
  chat: "conversations",
  spark: "spark",
  help: "help",
};

// Mirrors ping-widget/src/styles.css so the preview matches the real widget.
const RADIUS: Record<WidgetAppearance["corner"], { panel: number; msg: number; ctl: number }> = {
  rounded: { panel: 14, msg: 12, ctl: 8 },
  soft: { panel: 8, msg: 8, ctl: 6 },
  square: { panel: 2, msg: 3, ctl: 2 },
};
const FONTS: Record<WidgetAppearance["font"], string> = {
  system: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  rounded: 'ui-rounded, "SF Pro Rounded", "Nunito", "Varela Round", system-ui, sans-serif',
  serif: 'ui-serif, Georgia, Cambria, "Times New Roman", serif',
  mono: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
};

/** The widget's default second gradient colour: the accent, hue-shifted (ping-widget shiftHue). */
export function shiftHue(hex: string, degrees: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!m) return "#EC4899";
  const n = parseInt(m[1], 16);
  let r = (n >> 16) / 255;
  let g = ((n >> 8) & 255) / 255;
  let b = (n & 255) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  const sat = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  let h = 0;
  if (d) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
  }
  h = (h * 60 + degrees + 360) % 360;
  const c = (1 - Math.abs(2 * l - 1)) * sat;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const o = l - c / 2;
  [r, g, b] = h < 60 ? [c, x, 0] : h < 120 ? [x, c, 0] : h < 180 ? [0, c, x] : h < 240 ? [0, x, c] : h < 300 ? [x, 0, c] : [c, 0, x];
  return "#" + [r, g, b].map((v) => Math.round((v + o) * 255).toString(16).padStart(2, "0")).join("");
}

function Logo({ a, size }: { a: WidgetAppearance; size: number }) {
  const [broken, setBroken] = useState(false);
  if (a.logo_url && a.logo_url.startsWith("https://") && !broken) {
    return <img src={a.logo_url} alt="" className={s.wLogo} onError={() => setBroken(true)} />;
  }
  return <Icon name={launcherIcons[a.launcher]} size={size} />;
}

export function WidgetPreview({ a, host }: { a: WidgetAppearance; host: string }) {
  const [open, setOpen] = useState(true);
  const side = a.position === "right" ? { right: 20 } : { left: 20 };
  const dark = a.theme === "dark";
  const muted = dark ? "#a1a1aa" : "#71717a";
  const bg = dark ? "#111113" : "#ffffff";
  const border = dark ? "#2e2e34" : "#e4e4e7";
  const accent2 = a.accent_2 || shiftHue(a.accent, 40);
  const r = RADIUS[a.corner] ?? RADIUS.rounded;
  const hero = a.layout === "welcome";
  const compact = a.layout === "compact";
  const outline = a.bubble === "outline";

  const head: CSSProperties =
    hero
      ? { background: "transparent", color: "inherit" }
      : a.header_style === "gradient"
        ? { background: `linear-gradient(135deg, ${a.accent}, ${accent2})` }
        : a.header_style === "light"
          ? { background: bg, color: "inherit", borderBottom: `1px solid ${border}` }
          : { background: a.accent };
  const botBubble: CSSProperties = outline
    ? { background: "transparent", border: `1px solid ${border}`, borderRadius: r.msg }
    : { borderRadius: r.msg };
  const userBubble: CSSProperties = outline
    ? { background: "transparent", color: "inherit", border: `1px solid ${a.accent}`, borderRadius: r.msg }
    : { background: a.accent, borderRadius: r.msg };
  const panel: CSSProperties = {
    ...(a.position === "right" ? { right: 16 } : { left: 16 }),
    borderRadius: r.panel,
    overflow: "hidden",
    fontFamily: FONTS[a.font] ?? FONTS.system,
    width: compact ? 290 : a.size === "large" ? 360 : 320,
    ...(hero
      ? {
          background: `radial-gradient(120% 60% at 0% 0%, ${a.accent}38, transparent 60%), radial-gradient(120% 60% at 100% 0%, ${accent2}33, transparent 60%), ${bg}`,
        }
      : {}),
  };
  const lightHead = !hero && a.header_style === "light";

  return (
    <div>
      <div className={s.stageBar}>
        <span className={s.stageDots}>
          <span />
          <span />
          <span />
        </span>
        https://{host}
      </div>
      <div className={s.stage}>
        <div className={s.fakePage} aria-hidden="true">
          <div className={s.fakeLine} style={{ width: "40%", height: 14 }} />
          <div className={s.fakeLine} style={{ width: "90%" }} />
          <div className={s.fakeLine} style={{ width: "82%" }} />
          <div className={s.fakeLine} style={{ width: "86%" }} />
          <div className={s.fakeLine} style={{ width: "60%" }} />
        </div>

        {open && (
          <div className={`${s.widget} ${dark ? s.widgetDark : s.widgetLight}`} style={panel}>
            <div className={s.wHead} style={head}>
              {!compact && (
                <span
                  className={s.wAvatar}
                  style={{
                    borderRadius: r.ctl,
                    visibility: hero ? "hidden" : undefined,
                    ...(lightHead ? { background: `${a.accent}29`, color: a.accent } : {}),
                  }}
                >
                  <Logo a={a} size={15} />
                </span>
              )}
              <span className={s.wTitle} style={hero ? { visibility: "hidden" } : undefined}>
                <strong>{a.title || "Assistant"}</strong>
                <span>Typically replies instantly</span>
              </span>
              <button
                type="button"
                aria-label="Close preview widget"
                onClick={() => setOpen(false)}
                style={{ background: "transparent", border: 0, color: "inherit", cursor: "pointer" }}
              >
                <Icon name="close" size={14} />
              </button>
            </div>
            <div className={s.wBody} style={hero ? { minHeight: 300 } : compact ? { minHeight: 210, padding: 12 } : undefined}>
              {hero && (
                <div className={s.wHero}>
                  <span
                    className={s.wHeroLogo}
                    style={{ borderRadius: 18, boxShadow: `0 0 0 2px ${a.accent}, 0 8px 24px ${a.accent}40`, color: a.accent, background: bg }}
                  >
                    <Logo a={a} size={26} />
                  </span>
                  <strong>{a.title || "Assistant"}</strong>
                </div>
              )}
              <div className={s.wBot} style={botBubble}>
                {a.welcome}
              </div>
              {a.suggestions.filter(Boolean).length > 0 && (
                <div className={s.wChips}>
                  {a.suggestions.filter(Boolean).map((q) => (
                    <button key={q} type="button" className={s.wChip} style={{ borderColor: a.accent, color: "inherit", borderRadius: 999 }}>
                      {q}
                    </button>
                  ))}
                </div>
              )}
              {!hero && (
                <>
                  <div className={s.wUser} style={userBubble}>
                    Can I export my invoices?
                  </div>
                  <div className={s.wBot} style={botBubble}>
                    Yes, go to Settings → Billing → Invoices and click Export.
                    {a.show_sources && (
                      <div>
                        <span className={s.wSource} style={{ color: muted }}>
                          <Icon name="file" size={10} />
                          product-handbook.pdf
                        </span>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
            <div
              className={s.wInput}
              style={hero ? { borderTop: "2px solid transparent", borderImage: `linear-gradient(90deg, ${a.accent}, ${accent2}) 1` } : undefined}
            >
              <input placeholder={a.placeholder} aria-label="Preview message input" style={{ color: "inherit" }} />
              <button type="button" className={s.wSend} style={{ background: a.accent, borderRadius: r.ctl }} aria-label="Send">
                <Icon name="send" size={14} />
              </button>
            </div>
            {a.show_branding && <div className={s.wBrand}>Powered by Pingie</div>}
          </div>
        )}

        <button
          type="button"
          className={s.launcher}
          style={{ ...side, background: a.accent, borderRadius: "50%", overflow: "hidden" }}
          aria-label={open ? "Close widget" : "Open widget"}
          onClick={() => setOpen((o) => !o)}
        >
          {open ? <Icon name="close" size={22} /> : <Logo a={a} size={22} />}
        </button>
      </div>
    </div>
  );
}
