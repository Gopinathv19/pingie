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
import { DESIGN_FIELDS, type WidgetAppearance, type WidgetLayout } from "@/lib/types";
import { useAction } from "@/lib/use-api";
import { launcherIcons, shiftHue, WidgetPreview } from "./WidgetPreview";
import s from "./widget.module.css";

const ACCENTS = ["#7C3AED", "#2563EB", "#0EA5E9", "#059669", "#D97706", "#DC2626", "#DB2777", "#18181B"];

// What a free widget renders (the backend resets these for plans without custom design).
const DESIGN_DEFAULTS: Pick<WidgetAppearance, (typeof DESIGN_FIELDS)[number]> = {
  layout: "classic",
  header_style: "solid",
  accent_2: "",
  logo_url: "",
  corner: "rounded",
  bubble: "filled",
  size: "standard",
  font: "system",
};

const LAYOUTS: { key: WidgetLayout; label: string; hint: string }[] = [
  { key: "classic", label: "Classic", hint: "Header and chat" },
  { key: "welcome", label: "Welcome screen", hint: "Logo, name, gradient" },
  { key: "compact", label: "Compact", hint: "Smaller panel" },
];

function Segmented<T extends string>({ label, value, options, onChange }: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (v: T) => void;
}) {
  return (
    <div className="field">
      <span className="field-label">{label}</span>
      <div role="group" aria-label={label} className="segmented">
        {options.map(([k, text]) => (
          <button key={k} type="button" aria-pressed={value === k} onClick={() => onChange(k)}>
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

/** A tiny sketch of each layout for the picker. */
function LayoutThumb({ layout, accent, accent2 }: { layout: WidgetLayout; accent: string; accent2: string }) {
  if (layout === "welcome") {
    return (
      <span className={s.thumb} style={{ background: `linear-gradient(160deg, ${accent}40, transparent 60%)`, alignItems: "center", justifyContent: "center", gap: 3 }}>
        <i style={{ width: 12, height: 12, borderRadius: 4, border: `1.5px solid ${accent2}` }} />
        <i style={{ width: 22, height: 3, background: "var(--text-3)" }} />
      </span>
    );
  }
  const compact = layout === "compact";
  return (
    <span className={s.thumb} style={compact ? { width: 48, height: 38, margin: "4px 8px" } : undefined}>
      <i style={{ height: compact ? 7 : 10, background: accent }} />
      <span style={{ display: "flex", flexDirection: "column", gap: 3, padding: 4 }}>
        <i style={{ width: "60%", height: 4, background: "var(--border-strong)" }} />
        <i style={{ width: "45%", height: 4, background: accent, alignSelf: "flex-end" }} />
      </span>
    </span>
  );
}

export function AppearanceView() {
  const { bot, setBot } = useBot();
  const { org } = useSession();
  const [saved, setSaved] = useState<WidgetAppearance>(bot.appearance);
  const [a, setA] = useState<WidgetAppearance>(bot.appearance);
  const [upgradeFor, setUpgradeFor] = useState<string | null>(null);
  const action = useAction();
  const dirty = JSON.stringify(a) !== JSON.stringify(saved);
  const validAccent = /^#[0-9a-fA-F]{6}$/.test(a.accent);
  const validAccent2 = !a.accent_2 || /^#[0-9a-fA-F]{6}$/.test(a.accent_2);
  const validLogo = !a.logo_url || a.logo_url.startsWith("https://");
  const canRemoveBranding = org.usage.remove_branding;
  const customDesign = !!org.usage.custom_design;
  // Free widgets render the default design, whatever is stored.
  const preview: WidgetAppearance = {
    ...a,
    ...(customDesign ? {} : DESIGN_DEFAULTS),
    accent: validAccent ? a.accent : saved.accent,
    accent_2: validAccent2 ? a.accent_2 : "",
    logo_url: validLogo ? a.logo_url : "",
  };

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
      {upgradeFor && <UpgradeModal trigger={upgradeFor} onClose={() => setUpgradeFor(null)} />}
      <PageHeader
        title="Appearance"
        description="Customize how the chat widget looks and greets visitors. Changes preview live."
        actions={
          <>
            <button type="button" className="btn" disabled={!dirty || action.busy} onClick={() => setA(saved)}>
              Discard
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!dirty || !validAccent || !validAccent2 || !validLogo || action.busy}
              onClick={save}
            >
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

          <Panel title="Design" aside={<span className={s.proBadge}>PRO</span>}>
            <div className={`panel-body ${customDesign ? "" : s.designLocked}`}>
              {!customDesign && (
                <div className={s.lockNote}>
                  <span>Layouts, your logo, gradients, corners and fonts are available on Pro and above.</span>
                  <button type="button" className="btn btn-sm btn-primary" onClick={() => setUpgradeFor("custom widget design")}>
                    <Icon name="spark" size={12} />
                    Upgrade
                  </button>
                </div>
              )}
              <fieldset className={s.design} disabled={!customDesign}>
                <div className="field">
                  <span className="field-label">Layout</span>
                  <div className={s.optionGrid}>
                    {LAYOUTS.map((l) => (
                      <button
                        key={l.key}
                        type="button"
                        className={`${s.option} ${s.layoutPick}`}
                        aria-pressed={a.layout === l.key}
                        onClick={() => set("layout", l.key)}
                      >
                        <LayoutThumb layout={l.key} accent={preview.accent} accent2={preview.accent_2 || shiftHue(preview.accent, 40)} />
                        {l.label}
                        <small>{l.hint}</small>
                      </button>
                    ))}
                  </div>
                </div>

                <Segmented
                  label="Header"
                  value={a.header_style}
                  options={[["solid", "Solid"], ["gradient", "Gradient"], ["light", "Light"]]}
                  onChange={(v) => set("header_style", v)}
                />

                <div className="field">
                  <span className="field-label">Second color</span>
                  <div className={s.swatches}>
                    <button
                      type="button"
                      className="btn btn-sm"
                      aria-pressed={!a.accent_2}
                      onClick={() => set("accent_2", "")}
                    >
                      Automatic
                    </button>
                    {ACCENTS.filter((c) => c.toLowerCase() !== a.accent.toLowerCase()).map((c) => (
                      <button
                        key={c}
                        type="button"
                        className={s.swatch}
                        style={{ background: c }}
                        aria-label={`Second color ${c}`}
                        aria-pressed={a.accent_2.toLowerCase() === c.toLowerCase()}
                        onClick={() => set("accent_2", c)}
                      />
                    ))}
                    <input
                      className={`input mono ${s.hex}`}
                      value={a.accent_2}
                      placeholder={shiftHue(preview.accent, 40).toUpperCase()}
                      aria-label="Custom second color"
                      aria-invalid={!validAccent2}
                      onChange={(e) => set("accent_2", e.target.value)}
                    />
                  </div>
                  <span className="field-help" style={validAccent2 ? undefined : { color: "var(--danger-soft)" }}>
                    {validAccent2 ? "Used by the gradient header and the Welcome screen." : "Use a #RRGGBB color"}
                  </span>
                </div>

                <label className="field">
                  <span className="field-label">Logo URL</span>
                  <input
                    className="input"
                    maxLength={512}
                    value={a.logo_url}
                    placeholder="https://example.com/logo.png"
                    aria-invalid={!validLogo}
                    onChange={(e) => set("logo_url", e.target.value.trim())}
                  />
                  <span className="field-help" style={validLogo ? undefined : { color: "var(--danger-soft)" }}>
                    {validLogo
                      ? "A square image works best. Shown in the header, the launcher and the Welcome screen, instead of the icon."
                      : "The logo URL must start with https://"}
                  </span>
                </label>

                <Segmented
                  label="Corners"
                  value={a.corner}
                  options={[["rounded", "Rounded"], ["soft", "Soft"], ["square", "Square"]]}
                  onChange={(v) => set("corner", v)}
                />
                <Segmented
                  label="Message bubbles"
                  value={a.bubble}
                  options={[["filled", "Filled"], ["outline", "Outline"]]}
                  onChange={(v) => set("bubble", v)}
                />
                <Segmented
                  label="Panel size"
                  value={a.size}
                  options={[["standard", "Standard"], ["large", "Large"]]}
                  onChange={(v) => set("size", v)}
                />
                <Segmented
                  label="Font"
                  value={a.font}
                  options={[["system", "System"], ["rounded", "Rounded"], ["serif", "Serif"], ["mono", "Mono"]]}
                  onChange={(v) => set("font", v)}
                />
              </fieldset>
            </div>
          </Panel>

          <Panel title="Behavior">
            <div className="panel-body">
              <div className="toggle-row">
                <div>
                  <span className="field-label">Help Center</span>
                  <span className="field-help">
                    Let visitors browse and search your web pages and team answers in the widget. Choose what&apos;s
                    listed on the Sources page.
                  </span>
                </div>
                <Toggle label="Help Center" checked={a.help_center_enabled} onChange={(v) => set("help_center_enabled", v)} />
              </div>
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
                  <button type="button" className="btn btn-sm" onClick={() => setUpgradeFor("removing the Pingie branding badge")}>
                    <Icon name="spark" size={12} />
                    Upgrade
                  </button>
                )}
              </div>
            </div>
          </Panel>
        </div>

        <div className={s.previewCol}>
          <WidgetPreview a={preview} host={bot.domain} />
        </div>
      </div>
    </div>
  );
}
