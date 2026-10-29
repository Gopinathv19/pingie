"use client";

import { useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import type { WidgetAppearance } from "@/lib/types";
import s from "./widget.module.css";

export const launcherIcons: Record<WidgetAppearance["launcher"], IconName> = {
  chat: "conversations",
  spark: "spark",
  help: "help",
};

export function WidgetPreview({ a, host }: { a: WidgetAppearance; host: string }) {
  const [open, setOpen] = useState(true);
  const side = a.position === "right" ? { right: 20 } : { left: 20 };
  const muted = a.theme === "dark" ? "#a1a1aa" : "#71717a";

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
          <div
            className={`${s.widget} ${a.theme === "dark" ? s.widgetDark : s.widgetLight}`}
            style={a.position === "right" ? { right: 16 } : { left: 16 }}
          >
            <div className={s.wHead} style={{ background: a.accent }}>
              <span className={s.wAvatar}>
                <Icon name={launcherIcons[a.launcher]} size={15} />
              </span>
              <span className={s.wTitle}>
                <strong>{a.title || "Assistant"}</strong>
                <span>Typically replies instantly</span>
              </span>
              <button
                type="button"
                aria-label="Close preview widget"
                onClick={() => setOpen(false)}
                style={{ background: "transparent", border: 0, color: "#fff", cursor: "pointer" }}
              >
                <Icon name="close" size={14} />
              </button>
            </div>
            <div className={s.wBody}>
              <div className={s.wBot}>{a.welcome}</div>
              {a.suggestions.filter(Boolean).length > 0 && (
                <div className={s.wChips}>
                  {a.suggestions.filter(Boolean).map((q) => (
                    <button key={q} type="button" className={s.wChip} style={{ borderColor: a.accent, color: "inherit" }}>
                      {q}
                    </button>
                  ))}
                </div>
              )}
              <div className={s.wUser} style={{ background: a.accent }}>
                Can I export my invoices?
              </div>
              <div className={s.wBot}>
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
            </div>
            <div className={s.wInput}>
              <input placeholder={a.placeholder} aria-label="Preview message input" style={{ color: "inherit" }} />
              <button type="button" className={s.wSend} style={{ background: a.accent }} aria-label="Send">
                <Icon name="send" size={14} />
              </button>
            </div>
            {a.show_branding && <div className={s.wBrand}>Powered by Pingie</div>}
          </div>
        )}

        <button
          type="button"
          className={s.launcher}
          style={{ ...side, background: a.accent }}
          aria-label={open ? "Close widget" : "Open widget"}
          onClick={() => setOpen((o) => !o)}
        >
          <Icon name={open ? "close" : launcherIcons[a.launcher]} size={22} />
        </button>
      </div>
    </div>
  );
}
