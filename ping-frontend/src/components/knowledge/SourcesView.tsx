"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Icon, type IconName } from "@/components/Icon";
import { useBot } from "@/components/session/BotProvider";
import { KpiGrid } from "@/components/ui/KpiGrid";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { ErrorState, InlineError, Loading } from "@/components/ui/States";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { Toggle } from "@/components/ui/Toggle";
import { api } from "@/lib/api";
import { bytes, relativeTime, shortDate } from "@/lib/format";
import { botHref } from "@/lib/nav";
import type { Source, SourceType } from "@/lib/types";
import { useAction, useApi } from "@/lib/use-api";
import s from "./knowledge.module.css";
import { TeamAnswersDrawer } from "./TeamAnswers";

const typeIcon: Record<SourceType, IconName> = {
  pdf: "file",
  docx: "file",
  text: "file",
  page: "link",
  url: "link",
  sitemap: "globe",
};

type UrlMode = "url" | "sitemap";

function sizeLabel(src: Source) {
  if (src.type === "sitemap") return src.page_count ? `${src.page_count} pages` : "—";
  if (src.type === "url") return "1 page";
  return bytes(src.size_bytes);
}

/** The source holding answers taught by the team (backend answer_service.SOURCE_NAME). */
const isTeamAnswers = (src: Source) => src.type === "text" && src.name === "Team answers";

/** The widget's Help Center lists web pages and text files; PDF and DOCX stay answer-only. */
function HelpCenterCell({ src, busy, onToggle }: { src: Source; busy: boolean; onToggle: (on: boolean) => void }) {
  if (isTeamAnswers(src) || src.type === "pdf" || src.type === "docx") {
    return <span className="subtle" title="Only web pages and text files can be read in the Help Center">—</span>;
  }
  if (!src.readable) {
    return (
      <span className="subtle" style={{ fontSize: 12 }} title="Pages crawled before the Help Center existed have no readable copy yet">
        {src.status === "ready" ? "Re-sync to list" : "After indexing"}
      </span>
    );
  }
  return (
    <span className={s.helpCell}>
      <span style={busy ? { pointerEvents: "none" } : undefined}>
        <Toggle checked={src.in_help_center} onChange={onToggle} label={`Show ${src.name} in the Help Center`} />
      </span>
      {(src.helpful > 0 || src.unhelpful > 0) && (
        <span className="subtle mono" style={{ fontSize: 11 }} title="Visitors who said it answered / didn't answer their question">
          👍 {src.helpful} · 👎 {src.unhelpful}
        </span>
      )}
    </span>
  );
}

export function SourcesView() {
  const { bot, reload: reloadBot } = useBot();
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());
  const [dragging, setDragging] = useState(false);
  const [urlMode, setUrlMode] = useState<UrlMode>("url");
  const [url, setUrl] = useState("");
  const [answersOpen, setAnswersOpen] = useState(false);
  const [uploading, setUploading] = useState<string[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);
  const action = useAction();

  // Poll while anything is still being fetched or indexed by Memora.
  const [pollMs, setPollMs] = useState(0);
  const list = useApi(() => api.sources.list(bot.id), [bot.id], pollMs || undefined);
  const indexing = (list.data?.summary.indexing ?? 0) > 0;
  useEffect(() => setPollMs(indexing ? 4000 : 0), [indexing]);

  const summary = list.data?.summary;

  const addFiles = (files: FileList | null) =>
    action.run(async () => {
      const picked = Array.from(files ?? []);
      for (const f of picked) {
        setUploading((u) => [...u, f.name]);
        try {
          await api.sources.upload(bot.id, f);
        } finally {
          setUploading((u) => u.filter((n) => n !== f.name));
        }
      }
      await list.reload();
      reloadBot();
    });

  const addUrl = () =>
    action.run(async () => {
      if (!url.trim()) return;
      await api.sources.addUrl(bot.id, url.trim(), urlMode);
      setUrl("");
      await list.reload();
      reloadBot();
    });

  const onRow = (id: string, fn: () => Promise<unknown>) =>
    action.run(async () => {
      setBusyIds((b) => new Set(b).add(id));
      try {
        await fn();
        await list.reload();
      } finally {
        setBusyIds((b) => {
          const n = new Set(b);
          n.delete(id);
          return n;
        });
      }
    });

  const remove = (src: Source) => {
    if (!window.confirm(`Delete ${src.name}? Its chunks are removed from the bot's knowledge.`)) return;
    onRow(src.id, async () => {
      await api.sources.remove(bot.id, src.id);
      reloadBot();
    });
  };

  return (
    <div className="page">
      <PageHeader
        title="Sources"
        description={`Documents and pages ${bot.name} answers from. Memora chunks, embeds and indexes each one.`}
        actions={
          <Link href={botHref(bot.id, "test")} className="btn">
            <Icon name="test" size={14} />
            Test retrieval
          </Link>
        }
      />

      {summary && (
        <KpiGrid
          items={[
            {
              key: "sources",
              label: "Sources",
              value: String(summary.total),
              delta: summary.failed ? `${summary.failed} failed` : "—",
              tone: summary.failed ? "down" : "flat",
              sub: `${summary.ready} ready to answer`,
            },
            { key: "chunks", label: "Chunks indexed", value: summary.chunks.toLocaleString("en-US"), delta: "", tone: "flat", sub: "Searchable passages" },
            {
              key: "indexing",
              label: "Indexing",
              value: String(summary.indexing),
              delta: "",
              tone: "flat",
              sub: summary.indexing ? "Updating automatically" : "Nothing in progress",
            },
            { key: "sync", label: "Last sync", value: summary.last_sync ? relativeTime(summary.last_sync) : "—", delta: "", tone: "flat", sub: "Sitemaps can be re-synced anytime" },
          ]}
        />
      )}

      <InlineError message={action.error} />

      <div className={s.addGrid}>
        <Panel title="Upload files" aside={<span className="hint">PDF, DOCX, TXT, MD, CSV · up to 25 MB</span>}>
          <div className="panel-body">
            <button
              type="button"
              className={`${s.dropzone} ${dragging ? s.dropzoneActive : ""}`}
              onClick={() => fileInput.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setDragging(false);
                addFiles(e.dataTransfer.files);
              }}
            >
              <Icon name="upload" size={20} />
              {uploading.length ? (
                <span>Uploading {uploading[0]}…</span>
              ) : (
                <span>
                  <strong>Drop files here</strong> or click to browse
                </span>
              )}
            </button>
            <input
              ref={fileInput}
              type="file"
              multiple
              accept=".pdf,.docx,.txt,.md,.csv"
              hidden
              onChange={(e) => {
                addFiles(e.target.files);
                e.target.value = "";
              }}
            />
          </div>
        </Panel>

        <Panel
          title="Add from the web"
          aside={
            <div role="group" aria-label="URL type" className="segmented">
              <button type="button" aria-pressed={urlMode === "url"} onClick={() => setUrlMode("url")}>
                Single page
              </button>
              <button type="button" aria-pressed={urlMode === "sitemap"} onClick={() => setUrlMode("sitemap")}>
                Sitemap
              </button>
            </div>
          }
        >
          <form
            className="panel-body"
            onSubmit={(e) => {
              e.preventDefault();
              addUrl();
            }}
          >
            <label className="field">
              <span className="field-label">{urlMode === "url" ? "Page URL" : "Sitemap URL"}</span>
              <div className="input-group">
                <input
                  className="input mono"
                  placeholder={urlMode === "url" ? `https://${bot.domain}/security` : `https://${bot.domain}/sitemap.xml`}
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                />
                <button type="submit" className="btn btn-primary" disabled={!url.trim() || action.busy}>
                  Add
                </button>
              </div>
              <span className="field-help">
                {urlMode === "url"
                  ? "We fetch the page, strip navigation and index the main content."
                  : "Every page in the sitemap is crawled (respecting robots.txt) and indexed."}
              </span>
            </label>
          </form>
        </Panel>
      </div>

      <Panel
        title="Indexed sources"
        aside={
          <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
            {list.data && !list.data.items.some(isTeamAnswers) && (
              <button type="button" className="btn btn-sm" onClick={() => setAnswersOpen(true)}>
                <Icon name="plus" size={12} />
                Team answer
              </button>
            )}
            {summary && <span className="hint">{summary.total} total</span>}
          </div>
        }
      >
        {list.error && <ErrorState message={list.error.message} onRetry={list.reload} />}
        {!list.data && !list.error && <Loading />}
        {list.data && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Status</th>
                  <th style={{ textAlign: "right" }}>Chunks</th>
                  <th style={{ textAlign: "right" }}>Size</th>
                  <th>Updated</th>
                  <th title="Visitors can read it in the widget's Help Center">Help Center</th>
                  <th style={{ textAlign: "right" }}>
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {list.data.items.map((src) => (
                  <tr key={src.id} style={busyIds.has(src.id) ? { opacity: 0.5 } : undefined}>
                    <td style={{ maxWidth: 380 }}>
                      <div className={s.sourceName}>
                        <span className={s.typeIcon} aria-hidden="true">
                          <Icon name={typeIcon[src.type]} size={14} />
                        </span>
                        <span className={s.sourceTitle}>
                          {isTeamAnswers(src) ? (
                            <button
                              type="button"
                              className={s.sourceLink}
                              title="View and edit team answers"
                              onClick={() => setAnswersOpen(true)}
                            >
                              <strong>{src.name}</strong>
                              <span className={s.sourceHint}>View and edit answers</span>
                            </button>
                          ) : (
                            <strong title={src.url ?? src.name}>{src.name}</strong>
                          )}
                          {src.error && <span className={s.sourceErr}>{src.error}</span>}
                        </span>
                      </div>
                    </td>
                    <td>
                      {src.status === "queued" ? <span className="badge badge-accent">Fetching</span> : <StatusBadge status={src.status} />}
                      {(src.status === "indexing" || src.status === "queued") && (
                        <div className={s.progress} aria-label={`${src.progress}% indexed`}>
                          <div style={{ width: `${Math.max(src.progress, 4)}%` }} />
                        </div>
                      )}
                    </td>
                    <td className="num">{src.chunks ? src.chunks.toLocaleString("en-US") : "—"}</td>
                    <td className="num subtle">{sizeLabel(src)}</td>
                    <td className="subtle" style={{ fontSize: 12, whiteSpace: "nowrap" }}>
                      {shortDate(src.updated_at)}
                    </td>
                    <td>
                      <HelpCenterCell
                        src={src}
                        busy={busyIds.has(src.id)}
                        onToggle={(on) => onRow(src.id, () => api.sources.helpCenter(bot.id, src.id, on))}
                      />
                    </td>
                    <td>
                      <div className={s.actions}>
                        <button
                          type="button"
                          className={s.iconBtn}
                          aria-label={`Re-sync ${src.name}`}
                          title="Re-sync"
                          disabled={busyIds.has(src.id)}
                          onClick={() => onRow(src.id, () => api.sources.resync(bot.id, src.id))}
                        >
                          <Icon name="refresh" size={14} />
                        </button>
                        {isTeamAnswers(src) ? (
                          // Answers are deleted one by one in the drawer, so the
                          // dashboard and Memora stay in step.
                          <button
                            type="button"
                            className={s.iconBtn}
                            aria-label="Edit team answers"
                            title="Edit answers"
                            onClick={() => setAnswersOpen(true)}
                          >
                            <Icon name="edit" size={14} />
                          </button>
                        ) : (
                          <button
                            type="button"
                            className={s.iconBtn}
                            aria-label={`Delete ${src.name}`}
                            title="Delete"
                            disabled={busyIds.has(src.id)}
                            onClick={() => remove(src)}
                          >
                            <Icon name="trash" size={14} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {list.data.items.length === 0 && <div className="empty">No sources yet. Upload a file or add a URL to get started.</div>}
          </div>
        )}
      </Panel>

      {answersOpen && <TeamAnswersDrawer onChange={list.reload} onClose={() => setAnswersOpen(false)} />}
    </div>
  );
}
