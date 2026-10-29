"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "@/components/Icon";
import { useBot } from "@/components/session/BotProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { botHref } from "@/lib/nav";
import { useApi } from "@/lib/use-api";
import s from "./widget.module.css";

type Platform = "html" | "react" | "next" | "wordpress";

const PLATFORMS: { key: Platform; label: string }[] = [
  { key: "html", label: "HTML" },
  { key: "react", label: "React" },
  { key: "next", label: "Next.js" },
  { key: "wordpress", label: "WordPress" },
];

function snippet(p: Platform, botId: string, src: string) {
  switch (p) {
    case "html":
      return `<!-- Paste before </body> -->
<script
  src="${src}"
  data-bot-id="${botId}"
  defer
></script>`;
    case "react":
      return `import { useEffect } from "react";

export function PingieWidget() {
  useEffect(() => {
    const s = document.createElement("script");
    s.src = "${src}";
    s.dataset.botId = "${botId}";
    s.defer = true;
    document.body.appendChild(s);
    return () => s.remove();
  }, []);
  return null;
}`;
    case "next":
      return `// app/layout.tsx
import Script from "next/script";

<Script
  src="${src}"
  data-bot-id="${botId}"
  strategy="lazyOnload"
/>`;
    case "wordpress":
      return `1. Install the "Pingie Chat" plugin from Plugins → Add New.
2. Open Settings → Pingie.
3. Paste your bot ID: ${botId}
4. Click Save. The widget appears on every page.`;
  }
}

export function InstallView() {
  const { bot } = useBot();
  const [platform, setPlatform] = useState<Platform>("html");
  const [copied, setCopied] = useState<string | null>(null);
  const install = useApi(() => api.bots.install(bot.id), [bot.id]);
  const info = install.data;
  const verify: "checking" | "ok" | "idle" = install.loading ? "checking" : info?.detected ? "ok" : "idle";

  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* clipboard can be blocked; still show feedback */
    }
    setCopied(key);
    setTimeout(() => setCopied((c) => (c === key ? null : c)), 1500);
  };

  const code = snippet(platform, bot.id, info?.script_url ?? "https://cdn.pingie.app/widget.js");

  return (
    <div className="page">
      <PageHeader
        title="Install & embed"
        description="Add the widget to your site with one script tag. It only loads on allowed domains."
      />

      <Panel title="Setup">
        <div className={s.steps}>
          <div className={s.step}>
            <span className={`${s.stepNum} ${s.stepNumDone}`}>
              <Icon name="check" size={12} strokeWidth={2.4} />
            </span>
            <div className={s.stepBody}>
              <h3>Add your domain</h3>
              <p>
                The widget refuses to load anywhere else.{" "}
                <Link href={botHref(bot.id, "domains")}>Manage allowed domains →</Link>
              </p>
            </div>
          </div>

          <div className={s.step}>
            <span className={`${s.stepNum} ${s.stepNumDone}`}>
              <Icon name="check" size={12} strokeWidth={2.4} />
            </span>
            <div className={s.stepBody}>
              <h3>Paste the snippet</h3>
              <p>Choose your platform and add the code to every page where the bot should appear.</p>
              <div className="panel" style={{ background: "var(--bg)" }}>
                <div className={s.tabs} role="tablist">
                  {PLATFORMS.map((p) => (
                    <button
                      key={p.key}
                      type="button"
                      role="tab"
                      aria-selected={platform === p.key}
                      className={s.tab}
                      onClick={() => setPlatform(p.key)}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
                <div className={s.codeWrap}>
                  <pre className="code-block" style={{ border: 0 }}>
                    {code}
                  </pre>
                  <button type="button" className={`btn btn-sm ${s.copyBtn}`} onClick={() => copy("code", code)}>
                    <Icon name={copied === "code" ? "check" : "copy"} size={12} />
                    {copied === "code" ? "Copied" : "Copy"}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className={s.step}>
            <span className={`${s.stepNum} ${verify === "ok" ? s.stepNumDone : ""}`}>
              {verify === "ok" ? <Icon name="check" size={12} strokeWidth={2.4} /> : "3"}
            </span>
            <div className={s.stepBody}>
              <h3>Verify installation</h3>
              <p>We look for the widget on your domains and confirm it can reach the bot.</p>
              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn btn-sm"
                  disabled={verify === "checking"}
                  onClick={install.reload}
                >
                  <Icon name="refresh" size={12} />
                  {verify === "checking" ? "Checking…" : "Check again"}
                </button>
                {verify === "ok" && info && (
                  <span className="badge badge-ok">
                    <span className="dot" style={{ background: "var(--ok)", width: 6, height: 6 }} />
                    Detected on {info.detected_host} · {relativeTime(info.detected_at)}
                  </span>
                )}
                {verify === "idle" && info && <span className="badge">Not detected yet</span>}
              </div>
            </div>
          </div>
        </div>
      </Panel>

      <div className="grid-auto">
        <Panel title="Identifiers">
          {[
            ["Bot ID", bot.id],
            ["Public key", bot.public_key],
          ].map(([label, value]) => (
            <div key={label} className={s.keyRow}>
              <span className="muted">{label}</span>
              <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span className={s.keyValue}>{value}</span>
                <button type="button" className="btn btn-ghost btn-sm" aria-label={`Copy ${label}`} onClick={() => copy(label, value)}>
                  <Icon name={copied === label ? "check" : "copy"} size={13} />
                </button>
              </span>
            </div>
          ))}
        </Panel>

        <Panel title="Open programmatically">
          <div className="panel-body">
            <p className="muted" style={{ margin: 0, fontSize: 13, lineHeight: 1.5 }}>
              Trigger the widget from your own buttons, or pass the signed-in user so conversations are attributed.
            </p>
            <pre className="code-block">{`window.Pingie.open();
window.Pingie.identify({
  email: "jane@acme.com",
  name: "Jane Doe",
});`}</pre>
          </div>
        </Panel>
      </div>
    </div>
  );
}
