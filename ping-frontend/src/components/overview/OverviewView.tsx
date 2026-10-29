"use client";

import Link from "next/link";
import { useState } from "react";
import { Donut } from "@/components/charts/Donut";
import { LineChart } from "@/components/charts/LineChart";
import c from "@/components/charts/charts.module.css";
import { useBot } from "@/components/session/BotProvider";
import { KpiGrid } from "@/components/ui/KpiGrid";
import { PageHeader } from "@/components/ui/PageHeader";
import { Panel } from "@/components/ui/Panel";
import { ErrorState, Loading } from "@/components/ui/States";
import { api } from "@/lib/api";
import { botHref } from "@/lib/nav";
import type { Outcome, Overview, TimeRange } from "@/lib/types";
import { useApi } from "@/lib/use-api";

const RANGES: TimeRange[] = ["24h", "7d", "30d", "90d"];
const RANGE_CAPTION: Record<TimeRange, string> = {
  "24h": "in 24 hours",
  "7d": "in 7 days",
  "30d": "in 30 days",
  "90d": "in 90 days",
};
const OUTCOME_COLORS: Record<Outcome, string> = { answered: "#8B5CF6", partial: "#C4B5FD", fallback: "#F59E0B" };

export function OverviewView() {
  const { bot } = useBot();
  const [range, setRange] = useState<TimeRange>("30d");
  const { data, error, loading, reload } = useApi(() => api.bots.overview(bot.id, range), [bot.id, range]);

  return (
    <div className="page">
      <PageHeader
        title="Overview"
        description={`How ${bot.name} is answering visitors on ${bot.domain}.`}
        actions={
          <>
            <div role="group" aria-label="Time range" className="segmented">
              {RANGES.map((r) => (
                <button key={r} type="button" aria-pressed={r === range} onClick={() => setRange(r)}>
                  {r}
                </button>
              ))}
            </div>
            <button type="button" className="btn" onClick={reload} disabled={loading}>
              {loading ? "Refreshing…" : "Refresh"}
            </button>
          </>
        }
      />

      {error && <ErrorState message={error.message} onRetry={reload} />}
      {!data && !error && <Loading height={400} />}
      {data && <OverviewBody botId={bot.id} data={data} range={range} />}
    </div>
  );
}

function OverviewBody({ botId, data, range }: { botId: string; data: Overview; range: TimeRange }) {
  const maxPage = Math.max(1, ...data.top_pages.map((p) => p.value));
  const maxDay = Math.max(1, ...data.messages_per_day);
  const slices = data.outcomes.map((o) => ({ label: o.label, pct: o.pct, color: OUTCOME_COLORS[o.key] }));
  const empty = data.series_total === 0 && data.messages_14d === 0;

  return (
    <>
      <KpiGrid items={data.kpis} />

      {empty && (
        <div className="notice">
          No conversations yet. Add sources, set the bot live and{" "}
          <Link href={botHref(botId, "install")}>install the widget</Link> — numbers appear here as visitors chat.
        </div>
      )}

      <div className="split">
        <Panel
          title="Conversations"
          style={{ flex: "2 1 520px" }}
          aside={
            <div className={c.legend}>
              <span className={c.legendItem}>
                <span aria-hidden="true" className={c.swatch} style={{ background: "#8B5CF6" }} />
                Conversations
              </span>
              <span className={c.legendItem}>
                <span aria-hidden="true" className={c.swatch} style={{ background: "#F59E0B" }} />
                Unanswered
              </span>
            </div>
          }
        >
          <div className={c.lineBody}>
            <div className={c.total}>
              <span className={c.totalValue}>{data.series_total.toLocaleString("en-US")}</span>
              <span className={c.totalCaption}>{RANGE_CAPTION[range]}</span>
            </div>
            {data.series.length > 1 && <LineChart key={range} points={data.series} />}
          </div>
        </Panel>

        <Panel title="Answer outcomes" style={{ flex: "1 1 300px" }}>
          <div className="panel-body" style={{ gap: 18 }}>
            <Donut items={slices} value={`${data.resolved_pct}%`} label="resolved" />
            <div className={c.outcomeList}>
              {slices.map((o) => (
                <div key={o.label} className={c.outcomeRow}>
                  <span className={c.outcomeLabel}>
                    <span aria-hidden="true" className={c.swatch} style={{ background: o.color }} />
                    {o.label}
                  </span>
                  <span className="mono" style={{ fontWeight: 600 }}>
                    {o.pct}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Panel>
      </div>

      <div className="grid-auto">
        <Panel title="Messages per day">
          <div className="panel-body" style={{ gap: 8 }}>
            <div className={c.total}>
              <span style={{ fontSize: 22, fontWeight: 700 }}>{data.messages_14d.toLocaleString("en-US")}</span>
              <span style={{ fontSize: 12 }} className="muted">
                last 14 days
              </span>
            </div>
            <div role="img" aria-label="Bar chart of messages per day over the last 14 days" className={c.bars}>
              {data.messages_per_day.map((v, i) => (
                <div key={i} className={c.bar} title={`${v} messages`} style={{ height: `${Math.max(2, (v / maxDay) * 100)}%` }} />
              ))}
            </div>
            <div className={c.xAxis} style={{ paddingLeft: 0 }}>
              <span>14 days ago</span>
              <span>Today</span>
            </div>
          </div>
        </Panel>

        <Panel title="Top pages" aside={<span className="hint">where chats start</span>}>
          <div style={{ padding: "8px 18px 14px", display: "flex", flexDirection: "column" }}>
            {data.top_pages.length === 0 && <div className="empty">No chats yet</div>}
            {data.top_pages.map((p) => (
              <div key={p.path} className={c.meterRow}>
                <div className={c.meterHead}>
                  <span style={{ fontWeight: 500 }}>{p.path}</span>
                  <span style={{ fontWeight: 600 }}>{p.value}</span>
                </div>
                <div aria-hidden="true" className={c.meterTrack}>
                  <div className={c.meterFill} style={{ width: `${(p.value / maxPage) * 100}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel
          title="Knowledge gaps"
          aside={data.unanswered_count > 0 && <span className="badge badge-warn">{data.unanswered_count} unanswered</span>}
        >
          {data.knowledge_gaps.length === 0 && <div className="empty">No unanswered questions</div>}
          {data.knowledge_gaps.map((q) => (
            <div key={q} className="row">
              <span style={{ minWidth: 0 }}>{q}</span>
              <Link href={botHref(botId, "knowledge")} className="link-action">
                Add source →
              </Link>
            </div>
          ))}
        </Panel>
      </div>

      <Panel
        title="Top questions"
        aside={
          <Link href={botHref(botId, "conversations")} className="link-action">
            All conversations →
          </Link>
        }
      >
        {data.top_questions.length === 0 ? (
          <div className="empty">Questions visitors ask will be ranked here.</div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Question</th>
                  <th style={{ textAlign: "right" }}>Asked</th>
                  <th style={{ textAlign: "right" }}>Resolved</th>
                  <th>Top source</th>
                </tr>
              </thead>
              <tbody>
                {data.top_questions.map((q) => (
                  <tr key={q.text}>
                    <td style={{ fontWeight: 500 }}>{q.text}</td>
                    <td className="num" style={{ fontWeight: 600 }}>
                      {q.count}
                    </td>
                    <td className="num">{q.rate}</td>
                    <td className="mono" style={{ fontSize: 12, color: "var(--accent-softer)" }}>
                      {q.source ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
