"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import { UpgradeModal } from "@/components/billing/UpgradeModal";
import { useBot } from "@/components/session/BotProvider";
import { useSession } from "@/components/session/SessionProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { InlineError } from "@/components/ui/States";
import { Toggle } from "@/components/ui/Toggle";
import { api } from "@/lib/api";
import type { WidgetAppearance } from "@/lib/types";
import { useAction } from "@/lib/use-api";
import { launcherIcons, WidgetPreview } from "./WidgetPreview";
import s from "./widget.module.css";

const ACCENTS = ["#7C3AED", "#2563EB", "#0EA5E9", "#059669", "#D97706", "#DC2626", "#DB2777", "#18181B"];

export function AppearanceView() {
  const { bot, setBot } = useBot();
  const { org } = useSession();
  const [saved, setSaved] = useState<WidgetAppearance>(bot.appearance);
  const [a, setA] = useState<WidgetAppearance>(bot.appearance);
  const [showUpgrade, setShowUpgrade] = useState(false);
  const action = useAction();
  const dirty = JSON.stringify(a) !== JSON.stringify(saved);
  const validAccent = /^#[0-9a-fA-F]{6}$/.test(a.accent);
  const canRemoveBranding = org.usage.remove_branding;

  const set = <K extends keyof WidgetAppearance>(key: K, value: WidgetAppearance[K]) => setA((prev) => ({ ...prev, [key]: value }));
  const setSuggestion = (i: number, value: string) => set("suggestions", a.suggestions.map((q, j) => (j === i ? value : q)));

  const save = () =>
    action.run(async () => {
      const result = await api.bots.saveAppearance(bot.id, a);
      setSaved(result);
      setA(result);
      setBot({ ...bot, appearance: result });
    });

  return (
    <div className="page">
      {showUpgrade && <UpgradeModal trigger="removing the Pingie branding badge" onClose={() => setShowUpgrade(false)} />}
      <PageHeader
        title="Appearance"
        description="Customize how the chat widget looks and greets visitors. Changes preview live."
        actions={
          <>
            <button type="button" className="btn" disabled={!dirty || action.busy} onClick={() => setA(saved)}>
              Discard
            </button>
            <button type="button" className="btn btn-primary" disabled={!dirty || !validAccent || action.busy} onClick={save}>
              {action.busy ? "Saving…" : dirty ? "Save changes" : "Saved"}
            </button>
          </>
        }
      />
      <InlineError message={action.error} />

      <div className={s.layout}>
        <div className={s.formCol}>
          <Panel title="Content">
            <div className="panel-body">
              <label className="field">
                <span className="field-label">Header title</span>
                <input className="input" maxLength={60} value={a.title} onChange={(e) => set("title", e.target.value)} />
              </label>
              <label className="field">
                <span className="field-label">Welcome message</span>
                <textarea className="textarea" maxLength={500} value={a.welcome} onChange={(e) => set("welcome", e.target.value)} />
              </label>
              <label className="field">
                <span className="field-label">Input placeholder</span>
                <input className="input" maxLength={80} value={a.placeholder} onChange={(e) => set("placeholder", e.target.value)} />
              </label>
              <div className="field">
                <span className="field-label">Suggested questions</span>
                <div className={s.chipList}>
                  {a.suggestions.map((q, i) => (
                    <div key={i} className={s.chipRow}>
                      <input
                        className="input"
                        value={q}
                        maxLength={120}
                        aria-label={`Suggested question ${i + 1}`}
                        onChange={(e) => setSuggestion(i, e.target.value)}
                      />
                      <button
                        type="button"
                        className="btn btn-ghost"
                        aria-label="Remove question"
                        onClick={() => set("suggestions", a.suggestions.filter((_, j) => j !== i))}
                      >
                        <Icon name="close" size={14} />
                      </button>
                    </div>
                  ))}
                  {a.suggestions.length < 4 && (
                    <button
                      type="button"
                      className="btn btn-sm"
                      style={{ alignSelf: "flex-start" }}
                      onClick={() => set("suggestions", [...a.suggestions, ""])}
                    >
                      <Icon name="plus" size={12} />
                      Add question
                    </button>
                  )}
                </div>
                <span className="field-help">Shown as tappable chips under the welcome message. Up to 4.</span>
              </div>
            </div>
          </Panel>

          <Panel title="Style">
            <div className="panel-body">
              <div className="field">
                <span className="field-label">Accent color</span>
                <div className={s.swatches}>
                  {ACCENTS.map((c) => (
                    <button
                      key={c}
                      type="button"
                      className={s.swatch}
                      style={{ background: c }}
                      aria-label={c}
                      aria-pressed={a.accent.toLowerCase() === c.toLowerCase()}
                      onClick={() => set("accent", c)}
                    />
                  ))}
                  <input
                    className={`input mono ${s.hex}`}
                    value={a.accent}
                    aria-label="Custom hex color"
                    aria-invalid={!validAccent}
                    onChange={(e) => set("accent", e.target.value)}
                  />
                </div>
                {!validAccent && <span className="field-help" style={{ color: "var(--danger-soft)" }}>Use a #RRGGBB color</span>}
              </div>

              <div className="field">
                <span className="field-label">Theme</span>
                <div role="group" aria-label="Theme" className="segmented">
                  {(["dark", "light"] as const).map((t) => (
                    <button key={t} type="button" aria-pressed={a.theme === t} onClick={() => set("theme", t)}>
                      {t === "dark" ? "Dark" : "Light"}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field">
                <span className="field-label">Launcher icon</span>
                <div className={s.optionGrid}>
                  {(Object.keys(launcherIcons) as WidgetAppearance["launcher"][]).map((k) => (
                    <button key={k} type="button" className={s.option} aria-pressed={a.launcher === k} onClick={() => set("launcher", k)}>
                      <Icon name={launcherIcons[k]} size={18} />
                      {k === "chat" ? "Chat" : k === "spark" ? "Spark" : "Help"}
                    </button>
                  ))}
                </div>
              </div>

              <div className="field">
                <span className="field-label">Position</span>
                <div role="group" aria-label="Position" className="segmented">
                  {(["left", "right"] as const).map((p) => (
                    <button key={p} type="button" aria-pressed={a.position === p} onClick={() => set("position", p)}>
                      Bottom {p}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </Panel>

          <Panel title="Behavior">
            <div className="panel-body">
              <div className="toggle-row">
                <div>
                  <span className="field-label">Show cited sources</span>
                  <span className="field-help">Display the document each answer came from.</span>
                </div>
                <Toggle label="Show cited sources" checked={a.show_sources} onChange={(v) => set("show_sources", v)} />
              </div>
              <div className="toggle-row">
                <div>
                  <span className="field-label">Powered by Pingie badge</span>
                  <span className="field-help">
                    {canRemoveBranding
                      ? "Shown at the bottom of the widget."
                      : "Upgrade to Pro to remove the Pingie badge."}
                  </span>
                </div>
                {canRemoveBranding ? (
                  <Toggle label="Show branding" checked={a.show_branding} onChange={(v) => set("show_branding", v)} />
                ) : (
                  <button type="button" className="btn btn-sm" onClick={() => setShowUpgrade(true)}>
                    <Icon name="spark" size={12} />
                    Upgrade
                  </button>
                )}
              </div>
            </div>
          </Panel>
        </div>

        <div className={s.previewCol}>
          <WidgetPreview a={{ ...a, accent: validAccent ? a.accent : saved.accent }} host={bot.domain} />
        </div>
      </div>
    </div>
  );
}
