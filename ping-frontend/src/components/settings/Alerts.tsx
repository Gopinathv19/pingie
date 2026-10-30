"use client";

import { useState } from "react";
import { InlineError } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { AlertEvent } from "@/lib/types";
import { useAction } from "@/lib/use-api";
import s from "./settings.module.css";

const EVENTS: [AlertEvent, string][] = [
  ["wants_person", "A visitor wants to talk to a person"],
  ["lead", "A lead leaves their email"],
  ["disliked", "A visitor dislikes an answer"],
];

/** Where to post alerts and which events; "Send test alert" uses the saved URLs. */
export function Alerts({
  botId,
  slackUrl,
  webhookUrl,
  events,
  savedSlack,
  savedWebhook,
  canEdit,
  configured,
  onChange,
}: {
  botId: string;
  /** Viewers don't receive the URLs (they are credentials), only whether any is set. */
  canEdit: boolean;
  configured: boolean;
  slackUrl: string;
  webhookUrl: string;
  events: AlertEvent[];
  savedSlack: string;
  savedWebhook: string;
  onChange: (patch: { alert_slack_url?: string; alert_webhook_url?: string; alert_events?: AlertEvent[] }) => void;
}) {
  const test = useAction();
  const [results, setResults] = useState<Record<string, number | string> | null>(null);
  const unsaved = slackUrl !== savedSlack || webhookUrl !== savedWebhook;
  const toggle = (e: AlertEvent) =>
    onChange({ alert_events: events.includes(e) ? events.filter((x) => x !== e) : [...events, e] });

  if (!canEdit) {
    return (
      <div className="panel-body" style={{ maxWidth: 760 }}>
        <span className="field-help">
          {configured
            ? "Alerts are set up for this bot. Only editors can see or change where they're sent."
            : "No alerts are set up for this bot."}
        </span>
      </div>
    );
  }

  return (
    <div className="panel-body" style={{ maxWidth: 760 }}>
      <label className="field">
        <span className="field-label">Slack incoming webhook</span>
        <input
          className="input mono"
          placeholder="https://hooks.slack.com/services/…"
          value={slackUrl}
          onChange={(e) => onChange({ alert_slack_url: e.target.value })}
        />
        <span className="field-help">In Slack: Apps → Incoming Webhooks → Add to a channel, then paste the URL here.</span>
      </label>
      <label className="field">
        <span className="field-label">Webhook URL</span>
        <input
          className="input mono"
          placeholder="https://example.com/pingie-alerts"
          value={webhookUrl}
          onChange={(e) => onChange({ alert_webhook_url: e.target.value })}
        />
        <span className="field-help">
          Receives a JSON POST: <span className="mono">event, bot_id, conversation_id, visitor, email, text, url</span>.
        </span>
      </label>
      <div className="field">
        <span className="field-label">Send an alert when</span>
        {EVENTS.map(([e, label]) => (
          <label key={e} className={s.check}>
            <input type="checkbox" checked={events.includes(e)} onChange={() => toggle(e)} />
            {label}
          </label>
        ))}
      </div>
      <div className={s.memoryRow}>
        <span>
          {unsaved
            ? "Save your changes to test the new URLs."
            : savedSlack || savedWebhook
              ? "Send a test message to check the URLs work."
              : "Add a Slack or webhook URL to get alerts."}
          {results &&
            Object.entries(results).map(([k, v]) => (
              <span key={k} className={v === 200 || v === 204 ? s.ok : s.bad}>
                {" "}
                · {k}: {typeof v === "number" ? `HTTP ${v}` : v}
              </span>
            ))}
        </span>
        <button
          type="button"
          className="btn btn-sm"
          disabled={test.busy || unsaved || !(savedSlack || savedWebhook)}
          onClick={() => test.run(async () => setResults((await api.alerts.test(botId)).results))}
        >
          {test.busy ? "Sending…" : "Send test alert"}
        </button>
      </div>
      <InlineError message={test.error} />
    </div>
  );
}
