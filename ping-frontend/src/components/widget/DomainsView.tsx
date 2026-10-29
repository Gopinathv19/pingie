"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import { useBot } from "@/components/session/BotProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { ErrorState, Loading } from "@/components/ui/States";
import { Toggle } from "@/components/ui/Toggle";
import { api } from "@/lib/api";
import { relativeTime, shortDate } from "@/lib/format";
import { useAction, useApi } from "@/lib/use-api";

export function DomainsView() {
  const { bot, setBot, reload: reloadBot } = useBot();
  const domains = useApi(() => api.domains.list(bot.id), [bot.id]);
  const [value, setValue] = useState("");
  const add = useAction();
  const row = useAction();
  const toggle = useAction();

  const submit = () =>
    add.run(async () => {
      if (!value.trim()) return;
      await api.domains.add(bot.id, value.trim());
      setValue("");
      await domains.reload();
      reloadBot();
    });

  const remove = (id: string, host: string) => {
    if (!window.confirm(`Remove ${host}? The widget stops loading there.`)) return;
    row.run(async () => {
      await api.domains.remove(bot.id, id);
      await domains.reload();
      reloadBot();
    });
  };

  const setLocalhost = (v: boolean) => toggle.run(async () => setBot(await api.bots.update(bot.id, { allow_localhost: v })));

  return (
    <div className="page">
      <PageHeader
        title="Allowed domains"
        description={`${bot.name} only loads on these hosts. Requests from anywhere else are rejected.`}
      />

      <Panel title="Add a domain">
        <form
          className="panel-body"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
        >
          <label className="field">
            <span className="field-label">Hostname</span>
            <div className="input-group" style={{ maxWidth: 520 }}>
              <input
                className="input mono"
                placeholder="help.acme.com"
                value={value}
                onChange={(e) => {
                  setValue(e.target.value);
                  add.setError(null);
                }}
                aria-invalid={!!add.error}
              />
              <button type="submit" className="btn btn-primary" disabled={add.busy || !value.trim()}>
                <Icon name="plus" size={13} />
                Add domain
              </button>
            </div>
            <span className="field-help" style={add.error ? { color: "var(--danger-soft)" } : undefined}>
              {add.error || "Use *.acme.com to allow every subdomain. Don't include paths or protocols."}
            </span>
          </label>
        </form>
      </Panel>

      <Panel title="Domains" aside={domains.data && <span className="hint">{domains.data.length} allowed</span>}>
        {domains.error && <ErrorState message={domains.error.message} onRetry={domains.reload} />}
        {row.error && <ErrorState message={row.error} />}
        {!domains.data && !domains.error && <Loading />}
        {domains.data && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Host</th>
                  <th>Status</th>
                  <th>Last request</th>
                  <th>Added</th>
                  <th>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {domains.data.map((d) => (
                  <tr key={d.id}>
                    <td className="mono" style={{ fontWeight: 500 }}>
                      {d.host}
                    </td>
                    <td>
                      {d.receiving_traffic ? (
                        <span className="badge badge-ok">Receiving traffic</span>
                      ) : (
                        <span className="badge badge-warn">No traffic yet</span>
                      )}
                    </td>
                    <td className="subtle mono" style={{ fontSize: 12 }}>
                      {relativeTime(d.last_seen_at)}
                    </td>
                    <td className="subtle" style={{ fontSize: 12 }}>
                      {shortDate(d.created_at)}
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <button type="button" className="btn btn-ghost btn-sm" disabled={row.busy} onClick={() => remove(d.id, d.host)}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {domains.data.length === 0 && (
              <div className="empty">No domains yet. The widget won&apos;t load anywhere until you add one.</div>
            )}
          </div>
        )}
      </Panel>

      <Panel title="Development">
        <div className="panel-body">
          <div className="toggle-row">
            <div>
              <span className="field-label">Allow localhost</span>
              <span className="field-help">
                Lets the widget load on localhost and 127.0.0.1 while you build, even while the bot is a draft.
              </span>
            </div>
            <Toggle label="Allow localhost" checked={bot.allow_localhost} onChange={setLocalhost} />
          </div>
          {toggle.error && <ErrorState message={toggle.error} />}
        </div>
      </Panel>
    </div>
  );
}
