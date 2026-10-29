"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { useSession } from "@/components/session/SessionProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { InlineError } from "@/components/ui/States";
import { api } from "@/lib/api";
import { bytes } from "@/lib/format";
import { botHref } from "@/lib/nav";
import { useAction } from "@/lib/use-api";
import s from "../bots.module.css";

const STEPS = ["Basics", "Knowledge", "Launch"];

type SourceChoice = "crawl" | "upload" | "later";

const CHOICES: { key: SourceChoice; icon: IconName; title: string; body: string }[] = [
  { key: "crawl", icon: "globe", title: "Crawl my website", body: "We read your sitemap and index every help page." },
  { key: "upload", icon: "upload", title: "Upload documents", body: "PDF, DOCX, TXT or Markdown, up to 25 MB each." },
  { key: "later", icon: "more", title: "I'll add sources later", body: "Start with an empty bot and add knowledge after." },
];

export function NewBotWizard() {
  const router = useRouter();
  const { org } = useSession();
  const [step, setStep] = useState(0);
  const [name, setName] = useState("");
  const [site, setSite] = useState("");
  const [choice, setChoice] = useState<SourceChoice>("crawl");
  const [sitemap, setSitemap] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [progress, setProgress] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const { busy, error, run } = useAction();

  const host = site.trim().replace(/^https?:\/\//, "").replace(/\/.*$/, "");
  const canNext = step === 0 ? name.trim().length > 1 && host.includes(".") : true;

  const create = () =>
    run(async () => {
      setProgress("Creating bot…");
      const sitemapUrl = choice === "crawl" ? sitemap.trim() || `https://${host}/sitemap.xml` : undefined;
      const bot = await api.orgs.createBot(org.id, { name: name.trim(), domain: host, sitemap_url: sitemapUrl });
      if (choice === "upload") {
        for (const [i, f] of files.entries()) {
          setProgress(`Uploading ${i + 1} of ${files.length}: ${f.name}`);
          await api.sources.upload(bot.id, f);
        }
      }
      router.push(botHref(bot.id, choice === "later" ? "" : "knowledge"));
    });

  return (
    <div className={s.wizard}>
      <PageHeader title="Create a bot" description="Three steps. You can change everything later." />

      <ol className={s.stepper} style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {STEPS.map((label, i) => (
          <li
            key={label}
            className={`${s.stepTab} ${i === step ? s.stepTabActive : ""} ${i < step ? s.stepTabDone : ""}`}
            aria-current={i === step ? "step" : undefined}
          >
            <span className={s.stepIdx}>{i < step ? <Icon name="check" size={11} strokeWidth={2.6} /> : i + 1}</span>
            <span className={s.stepLabel}>{label}</span>
          </li>
        ))}
      </ol>

      {step === 0 && (
        <Panel title="Basics">
          <div className="panel-body">
            <label className="field">
              <span className="field-label">Bot name</span>
              <input className="input" autoFocus placeholder="Acme Help Center" value={name} onChange={(e) => setName(e.target.value)} />
              <span className="field-help">Visitors see this in the widget header.</span>
            </label>
            <label className="field">
              <span className="field-label">Website</span>
              <input className="input mono" placeholder="help.acme.com" value={site} onChange={(e) => setSite(e.target.value)} />
              <span className="field-help">Added to allowed domains so the widget can load there.</span>
            </label>
          </div>
        </Panel>
      )}

      {step === 1 && (
        <Panel title="Knowledge">
          <div className="panel-body">
            <div className={s.choiceGrid}>
              {CHOICES.map((c) => (
                <button key={c.key} type="button" className={s.choice} aria-pressed={choice === c.key} onClick={() => setChoice(c.key)}>
                  <strong>
                    <Icon name={c.icon} size={15} />
                    {c.title}
                  </strong>
                  {c.body}
                </button>
              ))}
            </div>
            {choice === "crawl" && (
              <label className="field">
                <span className="field-label">Sitemap URL</span>
                <input
                  className="input mono"
                  placeholder={`https://${host || "help.acme.com"}/sitemap.xml`}
                  value={sitemap}
                  onChange={(e) => setSitemap(e.target.value)}
                />
                <span className="field-help">Leave empty to use /sitemap.xml on your website.</span>
              </label>
            )}
            {choice === "upload" && (
              <>
                <button
                  type="button"
                  className="empty"
                  style={{ border: "1px dashed var(--border-strong)", background: "var(--bg)", cursor: "pointer", width: "100%", color: "inherit" }}
                  onClick={() => fileInput.current?.click()}
                >
                  <Icon name="upload" size={18} />
                  <div style={{ marginTop: 8 }}>Click to choose files</div>
                </button>
                <input
                  ref={fileInput}
                  type="file"
                  multiple
                  hidden
                  accept=".pdf,.docx,.txt,.md,.csv"
                  onChange={(e) => setFiles((prev) => [...prev, ...Array.from(e.target.files ?? [])])}
                />
                {files.map((f, i) => (
                  <div key={i} className="row" style={{ padding: "6px 0" }}>
                    <span className="mono" style={{ fontSize: 12 }}>
                      {f.name} <span className="subtle">· {bytes(f.size)}</span>
                    </span>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => setFiles(files.filter((_, j) => j !== i))}>
                      Remove
                    </button>
                  </div>
                ))}
              </>
            )}
          </div>
        </Panel>
      )}

      {step === 2 && (
        <Panel title="Ready to launch">
          <div className="panel-body">
            <div className="kpi-grid">
              <div className="kpi">
                <span className="kpi-label">Name</span>
                <span style={{ fontWeight: 700 }}>{name}</span>
              </div>
              <div className="kpi">
                <span className="kpi-label">Domain</span>
                <span className="mono">{host}</span>
              </div>
              <div className="kpi">
                <span className="kpi-label">Knowledge</span>
                <span>
                  {choice === "upload" ? `${files.length} file${files.length === 1 ? "" : "s"}` : CHOICES.find((c) => c.key === choice)!.title}
                </span>
              </div>
            </div>
            <p className="muted" style={{ margin: 0, fontSize: 13, lineHeight: 1.5 }}>
              Your bot starts as a <strong>draft</strong>. Indexing runs in the background. Test retrieval, customize the
              widget, then set it live and paste the embed snippet on {host}.
            </p>
            {busy && <div className="notice">{progress}</div>}
            <InlineError message={error} />
          </div>
        </Panel>
      )}

      <div className={s.wizardFoot}>
        {step === 0 ? (
          <Link href="/bots" className="btn">
            Cancel
          </Link>
        ) : (
          <button type="button" className="btn" disabled={busy} onClick={() => setStep(step - 1)}>
            Back
          </button>
        )}
        {step < STEPS.length - 1 ? (
          <button
            type="button"
            className="btn btn-primary"
            disabled={!canNext || (step === 1 && choice === "upload" && files.length === 0)}
            onClick={() => setStep(step + 1)}
          >
            Continue
          </button>
        ) : (
          <button type="button" className="btn btn-primary" disabled={busy} onClick={create}>
            {busy ? "Creating…" : "Create bot"}
          </button>
        )}
      </div>
    </div>
  );
}
