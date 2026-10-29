"use client";

import { useState } from "react";
import { Icon } from "@/components/Icon";
import { useBot } from "@/components/session/BotProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { InlineError, Loading } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { MessageOutcome, TestResult } from "@/lib/types";
import { useAction } from "@/lib/use-api";
import s from "./knowledge.module.css";

const OUTCOME: Record<MessageOutcome, { label: string; cls: string }> = {
  answered: { label: "Answered", cls: "badge-ok" },
  partial: { label: "Partial", cls: "badge-accent" },
  fallback: { label: "Fallback", cls: "badge-warn" },
  smalltalk: { label: "Small talk", cls: "" },
  lead: { label: "Lead", cls: "" },
  offline: { label: "Offline", cls: "" },
};

export function TestRetrievalView() {
  const { bot } = useBot();
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(4);
  const [threshold, setThreshold] = useState(bot.min_similarity);
  const [result, setResult] = useState<TestResult | null>(null);
  const action = useAction();

  const runTest = (q: string) => {
    if (!q.trim()) return;
    setQuery(q);
    action.run(async () => setResult(await api.sources.test(bot.id, q.trim(), topK, threshold)));
  };

  const suggestions = bot.appearance.suggestions;

  return (
    <div className="page">
      <PageHeader
        title="Test retrieval"
        description={`Ask a question and see exactly which passages Memora retrieves for ${bot.name}, and the answer Ping would give.`}
      />

      <Panel title="Query">
        <form
          className="panel-body"
          onSubmit={(e) => {
            e.preventDefault();
            runTest(query);
          }}
        >
          <div className={s.queryBar}>
            <input
              className="input"
              placeholder="Ask something a visitor might ask…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Test question"
            />
            <button type="submit" className="btn btn-primary" disabled={action.busy || !query.trim()}>
              <Icon name="test" size={14} />
              {action.busy ? "Running…" : "Run test"}
            </button>
          </div>
          {suggestions.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {suggestions.map((q) => (
                <button key={q} type="button" className="btn btn-sm" onClick={() => runTest(q)}>
                  {q}
                </button>
              ))}
            </div>
          )}
          <div className={s.settingsRow}>
            <label className="field" style={{ width: 140 }}>
              <span className="field-label">Top K</span>
              <select className="select" value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
                {[2, 3, 4, 5, 6, 8].map((k) => (
                  <option key={k} value={k}>
                    {k} chunks
                  </option>
                ))}
              </select>
            </label>
            <label className="field" style={{ flex: "1 1 240px", maxWidth: 320 }}>
              <span className="field-label">
                Similarity threshold <span className="mono subtle">{threshold.toFixed(2)}</span>
              </span>
              <input
                type="range"
                min={0}
                max={0.95}
                step={0.01}
                value={threshold}
                onChange={(e) => setThreshold(Number(e.target.value))}
                style={{ accentColor: "var(--accent)" }}
              />
            </label>
          </div>
          <InlineError message={action.error} />
        </form>
      </Panel>

      {action.busy && !result && <Loading label="Retrieving and reasoning…" />}

      {result && (
        <div className="split" style={action.busy ? { opacity: 0.6 } : undefined}>
          <Panel
            title="Retrieved chunks"
            style={{ flex: "3 1 480px" }}
            aside={
              <span className="hint">
                {result.chunks.filter((c) => c.above_threshold).length} of {result.chunks.length} above {result.threshold.toFixed(2)}
              </span>
            }
          >
            {result.chunks.length === 0 && (
              <div className="empty">Nothing matched. Add sources or check that indexing has finished.</div>
            )}
            {result.chunks.map((r) => (
              <div key={r.rank} className={`${s.result} ${r.above_threshold ? "" : s.resultBelow}`}>
                <div className={s.resultHead}>
                  <span className={s.resultSource}>
                    <span className={s.resultRank}>#{r.rank}</span>
                    <Icon name="file" size={12} />
                    {r.source}
                    {r.location && <span className={s.resultLoc}>· {r.location}</span>}
                  </span>
                  <span className={s.score}>
                    <span className={s.scoreTrack} aria-hidden="true">
                      <span
                        className={s.scoreFill}
                        style={{
                          display: "block",
                          width: `${Math.min(100, r.score * 100)}%`,
                          background: r.above_threshold ? "var(--accent)" : "var(--divider)",
                        }}
                      />
                    </span>
                    {r.score.toFixed(2)}
                  </span>
                </div>
                <p className={s.resultText}>{r.text}</p>
              </div>
            ))}
          </Panel>

          <Panel
            title="Generated answer"
            style={{ flex: "2 1 320px" }}
            aside={<span className={`badge ${OUTCOME[result.outcome].cls}`}>{OUTCOME[result.outcome].label}</span>}
          >
            <div className="panel-body">
              <div className="mono subtle" style={{ fontSize: 12 }}>
                Q: {result.query}
                {result.standalone_query !== result.query && <div>→ {result.standalone_query}</div>}
              </div>
              <div className={s.answer} style={{ whiteSpace: "pre-wrap", color: result.outcome === "fallback" ? "var(--warn-soft)" : undefined }}>
                {result.answer}
              </div>
              {result.citations.length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {result.citations.map((c, i) => (
                    <span key={i} className="badge badge-accent" style={{ textTransform: "none", letterSpacing: 0 }}>
                      {c.source_name}
                      {c.location ? ` · ${c.location}` : ""}
                    </span>
                  ))}
                </div>
              )}
              <div className={s.statLine}>
                <span>retrieval {result.retrieval_ms}ms</span>
                <span>generation {result.generation_ms}ms</span>
                <span>{result.chunks_in_context} chunks in context</span>
              </div>
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}
