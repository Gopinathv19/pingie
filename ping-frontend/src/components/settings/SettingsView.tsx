"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useBot } from "@/components/session/BotProvider";
import { useSession } from "@/components/session/SessionProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { InlineError } from "@/components/ui/States";
import { Toggle } from "@/components/ui/Toggle";
import { api } from "@/lib/api";
import type { Bot, BotUpdate, ModelTier } from "@/lib/types";
import { useAction } from "@/lib/use-api";

const EDITABLE = [
  "name",
  "status",
  "domain",
  "instructions",
  "model_tier",
  "tone",
  "reply_language",
  "min_similarity",
  "fallback_message",
  "collect_email",
  "handoff_email",
  "offline_message",
] as const;

type Form = Pick<Bot, (typeof EDITABLE)[number]>;

const TIER_LABELS: [ModelTier, string][] = [
  ["fast", "Fast: lowest latency"],
  ["balanced", "Balanced (recommended)"],
  ["best", "Best: highest quality"],
];

const pick = (bot: Bot): Form => Object.fromEntries(EDITABLE.map((k) => [k, bot[k]])) as Form;

export function SettingsView() {
  const router = useRouter();
  const { bot, setBot } = useBot();
  const { org } = useSession();
  const [saved, setSaved] = useState<Form>(pick(bot));
  const [form, setForm] = useState<Form>(pick(bot));
  const [confirm, setConfirm] = useState("");
  const save = useAction();
  const danger = useAction();

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }));
  const changes = Object.fromEntries(
    EDITABLE.filter((k) => form[k] !== saved[k]).map((k) => [k, form[k]]),
  ) as BotUpdate;
  const dirty = Object.keys(changes).length > 0;

  const submit = () =>
    save.run(async () => {
      const updated = await api.bots.update(bot.id, changes);
      setBot(updated);
      setSaved(pick(updated));
      setForm(pick(updated));
    });

  const clearHistory = () => {
    if (!window.confirm(`Permanently delete all ${bot.counts.conversations} conversations of ${bot.name}?`)) return;
    danger.run(async () => {
      await api.conversations.clear(bot.id);
      setBot({ ...bot, counts: { ...bot.counts, conversations: 0 } });
    });
  };

  const deleteBot = () =>
    danger.run(async () => {
      await api.bots.remove(bot.id);
      router.push("/bots");
    });

  return (
    <div className="page">
      <PageHeader
        title="Bot settings"
        description="Identity, answering behavior and fallbacks for this bot."
        actions={
          <>
            {dirty && (
              <button type="button" className="btn" onClick={() => setForm(saved)} disabled={save.busy}>
                Discard
              </button>
            )}
            <button type="button" className="btn btn-primary" disabled={!dirty || save.busy} onClick={submit}>
              {save.busy ? "Saving…" : dirty ? "Save changes" : "Saved"}
            </button>
          </>
        }
      />
      <InlineError message={save.error} />

      <Panel title="General">
        <div className="panel-body" style={{ maxWidth: 640 }}>
          <label className="field">
            <span className="field-label">Bot name</span>
            <input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">Website</span>
            <input className="input mono" value={form.domain} onChange={(e) => set("domain", e.target.value)} />
          </label>
          <label className="field">
            <span className="field-label">Bot ID</span>
            <input className="input mono" value={bot.id} readOnly style={{ color: "var(--text-3)" }} />
            <span className="field-help">Used in the embed snippet. It can&apos;t be changed.</span>
          </label>
          <div className="field">
            <span className="field-label">Status</span>
            <div role="group" aria-label="Status" className="segmented">
              {(["live", "paused", "draft"] as const).map((st) => (
                <button key={st} type="button" aria-pressed={form.status === st} onClick={() => set("status", st)}>
                  {st[0].toUpperCase() + st.slice(1)}
                </button>
              ))}
            </div>
            <span className="field-help">
              Live bots answer on allowed domains. Paused bots reply with the offline message. Drafts only load on localhost.
            </span>
          </div>
          {form.status === "paused" && (
            <label className="field">
              <span className="field-label">Offline message</span>
              <textarea
                className="textarea"
                rows={2}
                value={form.offline_message}
                placeholder="We're offline right now. Please check back later."
                onChange={(e) => set("offline_message", e.target.value)}
              />
            </label>
          )}
        </div>
      </Panel>

      <Panel title="Answering">
        <div className="panel-body" style={{ maxWidth: 760 }}>
          <label className="field">
            <span className="field-label">Instructions</span>
            <textarea
              className="textarea mono"
              rows={6}
              value={form.instructions}
              onChange={(e) => set("instructions", e.target.value)}
              style={{ fontSize: 12 }}
            />
            <span className="field-help">Sent with every question, before the retrieved passages.</span>
          </label>
          <div className="split">
            <label className="field" style={{ flex: "1 1 200px" }}>
              <span className="field-label">Model</span>
              <select className="select" value={form.model_tier} onChange={(e) => set("model_tier", e.target.value as Form["model_tier"])}>
                {TIER_LABELS.map(([tier, label]) => {
                  const locked = !org.allowed_model_tiers.includes(tier);
                  return (
                    <option key={tier} value={tier} disabled={locked}>
                      {label}
                      {locked ? " (upgrade to unlock)" : ""}
                    </option>
                  );
                })}
              </select>
            </label>
            <label className="field" style={{ flex: "1 1 200px" }}>
              <span className="field-label">Tone</span>
              <select className="select" value={form.tone} onChange={(e) => set("tone", e.target.value as Form["tone"])}>
                <option value="friendly">Friendly</option>
                <option value="professional">Professional</option>
                <option value="concise">Concise</option>
              </select>
            </label>
            <label className="field" style={{ flex: "1 1 200px" }}>
              <span className="field-label">Reply language</span>
              <select
                className="select"
                value={form.reply_language}
                onChange={(e) => set("reply_language", e.target.value as Form["reply_language"])}
              >
                <option value="auto">Match the visitor</option>
                <option value="en">English</option>
                <option value="hi">Hindi</option>
                <option value="ta">Tamil</option>
              </select>
            </label>
          </div>
          <label className="field" style={{ maxWidth: 360 }}>
            <span className="field-label">
              Similarity threshold <span className="mono subtle">{form.min_similarity.toFixed(2)}</span>
            </span>
            <input
              type="range"
              min={0}
              max={0.95}
              step={0.01}
              value={form.min_similarity}
              onChange={(e) => set("min_similarity", Number(e.target.value))}
              style={{ accentColor: "var(--accent)" }}
            />
            <span className="field-help">Passages scoring below this are ignored. Higher means fewer, safer answers.</span>
          </label>
        </div>
      </Panel>

      <Panel title="Fallback & handoff">
        <div className="panel-body" style={{ maxWidth: 760 }}>
          <label className="field">
            <span className="field-label">Fallback message</span>
            <textarea
              className="textarea"
              rows={3}
              value={form.fallback_message}
              placeholder="I couldn't find that in our documentation. Leave your email and the team will get back to you."
              onChange={(e) => set("fallback_message", e.target.value)}
            />
            <span className="field-help">Used when the sources don&apos;t answer the question. Leave empty for the default.</span>
          </label>
          <div className="toggle-row">
            <div>
              <span className="field-label">Collect email on fallback</span>
              <span className="field-help">Captured leads appear under Conversations → Handoffs.</span>
            </div>
            <Toggle label="Collect email on fallback" checked={form.collect_email} onChange={(v) => set("collect_email", v)} />
          </div>
          {form.collect_email && (
            <label className="field">
              <span className="field-label">Send handoffs to</span>
              <input
                className="input mono"
                type="email"
                placeholder="support@acme.com"
                value={form.handoff_email}
                onChange={(e) => set("handoff_email", e.target.value)}
                style={{ maxWidth: 360 }}
              />
            </label>
          )}
        </div>
      </Panel>

      {bot.access_role === "owner" && (
        <section className="panel" style={{ borderColor: "var(--danger-border)" }} aria-labelledby="danger">
          <div className="panel-header" style={{ borderColor: "var(--danger-border)" }}>
            <h2 id="danger" style={{ color: "var(--danger-soft)" }}>
              Danger zone
            </h2>
          </div>
          {danger.error && (
            <div style={{ padding: "12px 18px 0" }}>
              <InlineError message={danger.error} />
            </div>
          )}
          <div className="row" style={{ padding: "14px 18px", flexWrap: "wrap" }}>
            <div>
              <div style={{ fontWeight: 600 }}>Clear conversation history</div>
              <div className="subtle" style={{ fontSize: 12, marginTop: 3 }}>
                Permanently removes all {bot.counts.conversations.toLocaleString("en-US")} conversations and leads.
              </div>
            </div>
            <button type="button" className="btn btn-danger" disabled={danger.busy || bot.counts.conversations === 0} onClick={clearHistory}>
              Clear history
            </button>
          </div>
          <div className="row" style={{ padding: "14px 18px", flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 300px" }}>
              <div style={{ fontWeight: 600 }}>Delete this bot</div>
              <div className="subtle" style={{ fontSize: 12, marginTop: 3 }}>
                Deletes the bot, its conversations, and its sources and embeddings in Memora. Type{" "}
                <span className="mono">{bot.name}</span> to confirm.
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <input
                className="input"
                style={{ width: 220 }}
                placeholder={bot.name}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                aria-label="Type bot name to confirm"
              />
              <button type="button" className="btn btn-danger" disabled={confirm !== bot.name || danger.busy} onClick={deleteBot}>
                {danger.busy ? "Deleting…" : "Delete bot"}
              </button>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
