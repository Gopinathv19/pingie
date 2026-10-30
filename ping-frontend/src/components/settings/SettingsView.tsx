"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useBot } from "@/components/session/BotProvider";
import { useSession } from "@/components/session/SessionProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { InlineError } from "@/components/ui/States";
import { Toggle } from "@/components/ui/Toggle";
import { api } from "@/lib/api";
import type { AnswerStrictness, Bot, BotUpdate, BusinessHours as Hours, HandoffMode, MemoryMode, ModelTier } from "@/lib/types";
import { useAction } from "@/lib/use-api";
import { Alerts } from "./Alerts";
import { BusinessHours } from "./BusinessHours";
import { SavedReplies } from "./SavedReplies";
import s from "./settings.module.css";

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
  "handoff_mode",
  "memory_mode",
  "answer_strictness",
  "topic_guard",
  "blocked_topics",
  "off_topic_message",
  "business_hours",
  "alert_slack_url",
  "alert_webhook_url",
  "alert_events",
] as const;

type Form = Pick<Bot, (typeof EDITABLE)[number]>;

const TIER_LABELS: [ModelTier, string][] = [
  ["fast", "Fast: lowest latency"],
  ["balanced", "Balanced (recommended)"],
  ["best", "Best: highest quality"],
];

const HANDOFF_MODES: { mode: HandoffMode; title: string; detail: string }[] = [
  {
    mode: "instant",
    title: "Connect right away",
    detail: "Asking for a person hands the chat to your team at once. Best for urgent support.",
  },
  {
    mode: "offer",
    title: "Offer a button first (recommended)",
    detail: "The bot replies with a \u201cTalk to a person\u201d button. Clicking it, or asking again, hands the chat over.",
  },
  {
    mode: "bot_first",
    title: "Let the bot try first",
    detail: "The bot answers from your knowledge, with the button under its reply. Asking a second time hands the chat over.",
  },
];

const MEMORY_MODES: { mode: MemoryMode; title: string; detail: string }[] = [
  {
    mode: "manual",
    title: "Manual only (recommended)",
    detail: "The bot learns nothing on its own. It only learns what a teammate saves with \u201cSave as knowledge\u201d in a conversation.",
  },
  {
    mode: "review",
    title: "Review first",
    detail: "Finished chats a teammate answered wait under Conversations \u2192 To review. The bot learns one only after someone approves it.",
  },
  {
    mode: "auto",
    title: "Automatic",
    detail: "Finished chats a teammate answered are learned on their own. Very short replies and disliked chats are skipped. Bad answers can still slip in.",
  },
];

const STRICTNESS: { value: AnswerStrictness; title: string; detail: string }[] = [
  { value: "strict", title: "Strict", detail: "Answers only when the docs clearly cover the question; otherwise falls back. Fewest mistakes." },
  { value: "balanced", title: "Balanced (recommended)", detail: "Answers from relevant passages and says when it only found part of the answer." },
  { value: "helpful", title: "Helpful", detail: "Uses more loosely related passages and explains terms in them. More answers, slightly more risk." },
];

const browserZone = () => {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
};

const pick = (bot: Bot): Form => {
  const form = Object.fromEntries(EDITABLE.map((k) => [k, bot[k]])) as Form;
  // A backend without the setting (e.g. mid-restart) leaves it undefined; show the default.
  form.handoff_mode ??= "offer";
  form.memory_mode ??= "manual";
  form.answer_strictness ??= "balanced";
  form.alert_events ??= ["wants_person", "lead", "disliked"];
  const hours = bot.business_hours ?? {};
  form.business_hours = { enabled: !!hours.enabled, timezone: hours.timezone || browserZone(), days: hours.days ?? {} };
  return form;
};

export function SettingsView() {
  const router = useRouter();
  const { bot, setBot } = useBot();
  const { org } = useSession();
  const [saved, setSaved] = useState<Form>(pick(bot));
  const [form, setForm] = useState<Form>(pick(bot));
  const [confirm, setConfirm] = useState("");
  const save = useAction();
  const danger = useAction();
  const memoryAction = useAction();

  const set = <K extends keyof Form>(key: K, value: Form[K]) => setForm((f) => ({ ...f, [key]: value }));
  // Objects and lists (business hours, alert events) compare by value.
  const same = (a: unknown, b: unknown) => (typeof a === "object" ? JSON.stringify(a) === JSON.stringify(b) : a === b);
  const changes = Object.fromEntries(
    EDITABLE.filter((k) => !same(form[k], saved[k])).map((k) => [k, form[k]]),
  ) as BotUpdate;
  const dirty = Object.keys(changes).length > 0;

  const submit = () =>
    save.run(async () => {
      const updated = await api.bots.update(bot.id, changes);
      setBot(updated);
      setSaved(pick(updated));
      setForm(pick(updated));
    });

  const forgetLearned = () => {
    const n = bot.memory?.learned ?? 0;
    if (!window.confirm(`Remove all ${n} learned chat${n === 1 ? "" : "s"} from ${bot.name}'s knowledge? Chats you saved with Save as knowledge stay.`)) return;
    memoryAction.run(async () => {
      await api.memory.forget(bot.id);
      setBot({ ...bot, memory: { learned: 0, pending: bot.memory?.pending ?? 0 } });
    });
  };

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
          <div className="field">
            <span className="field-label">How careful should answers be?</span>
            <div role="radiogroup" aria-label="How careful should answers be?" className={s.modes}>
              {STRICTNESS.map((m) => (
                <label key={m.value} className={`${s.mode} ${form.answer_strictness === m.value ? s.modeActive : ""}`}>
                  <input
                    type="radio"
                    name="answer_strictness"
                    value={m.value}
                    checked={form.answer_strictness === m.value}
                    onChange={() => set("answer_strictness", m.value)}
                  />
                  <span>
                    <span className={s.modeTitle}>{m.title}</span>
                    <span className="field-help">{m.detail}</span>
                  </span>
                </label>
              ))}
            </div>
          </div>
          <div className="toggle-row">
            <div>
              <span className="field-label">Only answer questions about {bot.name}</span>
              <span className="field-help">
                Politely declines unrelated questions (food, jokes, other companies) instead of asking for an email.
              </span>
            </div>
            <Toggle label={`Only answer questions about ${bot.name}`} checked={form.topic_guard} onChange={(v) => set("topic_guard", v)} />
          </div>
          {form.topic_guard && (
            <div className="split">
              <label className="field" style={{ flex: "1 1 260px" }}>
                <span className="field-label">Always decline these topics</span>
                <textarea
                  className="textarea"
                  rows={3}
                  placeholder={"food orders\njokes\ncompetitors"}
                  value={form.blocked_topics}
                  onChange={(e) => set("blocked_topics", e.target.value)}
                />
                <span className="field-help">One per line. Declined straight away, without searching your knowledge.</span>
              </label>
              <label className="field" style={{ flex: "1 1 260px" }}>
                <span className="field-label">Reply for off-topic questions</span>
                <textarea
                  className="textarea"
                  rows={3}
                  placeholder={`Sorry, I can only help with questions about ${bot.name}. Ask me anything about ${bot.domain} and I'll help.`}
                  value={form.off_topic_message}
                  onChange={(e) => set("off_topic_message", e.target.value)}
                />
                <span className="field-help">Leave empty for the default.</span>
              </label>
            </div>
          )}
          <details className={s.advanced}>
            <summary>Advanced</summary>
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
          </details>
        </div>
      </Panel>

      <Panel title="Fallback & handoff">
        <div className="panel-body" style={{ maxWidth: 760 }}>
          <div className="field">
            <span className="field-label">When a visitor asks for a person</span>
            <div role="radiogroup" aria-label="When a visitor asks for a person" className={s.modes}>
              {HANDOFF_MODES.map((m) => (
                <label key={m.mode} className={`${s.mode} ${form.handoff_mode === m.mode ? s.modeActive : ""}`}>
                  <input
                    type="radio"
                    name="handoff_mode"
                    value={m.mode}
                    checked={form.handoff_mode === m.mode}
                    onChange={() => set("handoff_mode", m.mode)}
                  />
                  <span>
                    <span className={s.modeTitle}>{m.title}</span>
                    <span className="field-help">{m.detail}</span>
                  </span>
                </label>
              ))}
            </div>
            <span className={bot.agents_online ? s.onlineNow : s.offlineNow}>
              <span className="dot" style={{ background: bot.agents_online ? "var(--ok)" : "var(--warn)" }} />
              {bot.outside_hours
                ? `Outside business hours${bot.next_opening ? ` (back ${bot.next_opening})` : ""}. A handover flags the chat and emails the team, even with Live on.`
                : bot.agents_online
                ? "Someone on your team is online, so a handover connects them right away."
                : "Nobody is online right now. Switch Live on in the top bar to take chats; until then a handover flags the chat as \u201cWants a person\u201d in Conversations and emails the team."}
            </span>
          </div>
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

      <Panel title="Business hours">
        <BusinessHours value={form.business_hours as Hours} onChange={(v) => set("business_hours", v)} />
      </Panel>

      <Panel title="Alerts">
        <Alerts
          botId={bot.id}
          slackUrl={form.alert_slack_url}
          webhookUrl={form.alert_webhook_url}
          events={form.alert_events}
          savedSlack={saved.alert_slack_url}
          savedWebhook={saved.alert_webhook_url}
          canEdit={bot.access_role !== "viewer"}
          configured={bot.alerts_configured}
          onChange={(patch) => setForm((f) => ({ ...f, ...patch }))}
        />
      </Panel>

      <Panel title="Saved replies">
        <SavedReplies botId={bot.id} canEdit={bot.access_role !== "viewer"} />
      </Panel>

      <Panel title="Learning from conversations">
        <div className="panel-body" style={{ maxWidth: 760 }}>
          <div className="field">
            <span className="field-label">Learn from chats a teammate answered</span>
            <div role="radiogroup" aria-label="Learn from chats a teammate answered" className={s.modes}>
              {MEMORY_MODES.map((m) => (
                <label key={m.mode} className={`${s.mode} ${form.memory_mode === m.mode ? s.modeActive : ""}`}>
                  <input
                    type="radio"
                    name="memory_mode"
                    value={m.mode}
                    checked={form.memory_mode === m.mode}
                    onChange={() => set("memory_mode", m.mode)}
                  />
                  <span>
                    <span className={s.modeTitle}>{m.title}</span>
                    <span className="field-help">{m.detail}</span>
                  </span>
                </label>
              ))}
            </div>
            <span className="field-help">
              &ldquo;Save as knowledge&rdquo; in a conversation always works, whatever you choose. It&apos;s also the way to
              share an answer with your other bots.
            </span>
          </div>
          <div className={s.memoryRow}>
            <span>
              <strong>{bot.memory?.learned ?? 0}</strong> chat{(bot.memory?.learned ?? 0) === 1 ? "" : "s"} learned
              {" \u00b7 "}
              {(bot.memory?.pending ?? 0) > 0 ? (
                <Link href={`/bots/${bot.id}/conversations?filter=review`}>{bot.memory.pending} waiting for review</Link>
              ) : (
                <>0 waiting for review</>
              )}
            </span>
            <button
              type="button"
              className="btn btn-sm"
              disabled={memoryAction.busy || (bot.memory?.learned ?? 0) === 0}
              onClick={forgetLearned}
            >
              {memoryAction.busy ? "Forgetting\u2026" : "Forget learned chats"}
            </button>
          </div>
          <InlineError message={memoryAction.error} />
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
