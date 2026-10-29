"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { useBot } from "@/components/session/BotProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, InlineError, Loading } from "@/components/ui/States";
import { api } from "@/lib/api";
import { clock, dayTime, duration, relativeTime } from "@/lib/format";
import type {
  ChatMessage,
  ChatStatus,
  ConversationDetail,
  ConversationFilter,
  ConversationSummary,
  KnowledgeDraftItem,
  MessageOutcome,
} from "@/lib/types";
import { useAction, useApi } from "@/lib/use-api";
import s from "./conversations.module.css";

const FILTERS: { key: ConversationFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "live", label: "Live" },
  { key: "unanswered", label: "Unanswered" },
  { key: "down", label: "Disliked" },
  { key: "handoff", label: "Handoffs" },
];

const outcomeBadge: Record<MessageOutcome, { label: string; cls: string }> = {
  answered: { label: "Answered", cls: "badge-ok" },
  partial: { label: "Partial", cls: "badge-accent" },
  fallback: { label: "Fallback", cls: "badge-warn" },
  smalltalk: { label: "Small talk", cls: "" },
  lead: { label: "Lead captured", cls: "badge-accent" },
  offline: { label: "Offline", cls: "" },
};

const LIVE: ChatStatus[] = ["waiting", "human"];

function StatusPill({ status, assignedTo, since }: { status: ChatStatus; assignedTo: string | null; since: string | null }) {
  if (status === "waiting") {
    return <span className={`${s.pill} ${s.pillWaiting}`}>Waiting{since ? ` · ${relativeTime(since)}` : ""}</span>;
  }
  if (status === "human") return <span className={`${s.pill} ${s.pillHuman}`}>With {assignedTo ?? "an agent"}</span>;
  if (status === "closed") return <span className={s.pill}>Ended</span>;
  return null;
}

export function ConversationsView() {
  const { bot } = useBot();
  const [filter, setFilter] = useState<ConversationFilter>(bot.counts.live > 0 ? "live" : "all");
  const [query, setQuery] = useState("");
  const [q, setQ] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [more, setMore] = useState<ConversationSummary[]>([]);
  const [cursor, setCursor] = useState<string | null>(null);
  const loadMore = useAction();

  // ?c=<id> opens a conversation directly (links from notifications and the Live menu).
  useEffect(() => {
    const c = new URLSearchParams(window.location.search).get("c");
    if (c) setSelectedId(c);
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setQ(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  const list = useApi(() => api.conversations.list(bot.id, filter, q), [bot.id, filter, q], 8000);
  useEffect(() => {
    setMore([]);
    setCursor(list.data?.next_before ?? null);
  }, [list.data?.next_before]);

  const items = [...(list.data?.items ?? []), ...more];
  const selected = items.find((c) => c.id === selectedId);
  const openId = selected?.id ?? selectedId ?? items[0]?.id ?? null;

  const fetchMore = () =>
    loadMore.run(async () => {
      if (!cursor) return;
      const page = await api.conversations.list(bot.id, filter, q, cursor);
      setMore((m) => [...m, ...page.items]);
      setCursor(page.next_before);
    });

  return (
    <div className="page">
      <PageHeader
        title="Conversations"
        description={`Every chat visitors have had with ${bot.name}. Take over any chat to reply as a person.`}
        actions={
          <a className="btn" href={api.conversations.exportUrl(bot.id)} download>
            Export CSV
          </a>
        }
      />

      {list.error && <ErrorState message={list.error.message} onRetry={list.reload} />}

      <div className={s.inbox}>
        <div className={s.listCol}>
          <div className={s.listTools}>
            <input
              className="input"
              type="search"
              placeholder="Search messages or visitors…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              aria-label="Search conversations"
            />
            <div role="group" aria-label="Filter" className="segmented" style={{ width: "100%" }}>
              {FILTERS.map((f) => (
                <button key={f.key} type="button" style={{ flex: "1 1 auto", padding: "0 6px", minWidth: 0 }} aria-pressed={f.key === filter} onClick={() => setFilter(f.key)}>
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <div className={s.list}>
            {!list.data && !list.error && <Loading />}
            {list.data && items.length === 0 && (
              <div className="empty">
                {filter === "live"
                  ? "No live chats. Visitors can ask for a person when the bot can't answer."
                  : q || filter !== "all"
                    ? "No conversations match."
                    : "No conversations yet."}
              </div>
            )}
            {items.map((c) => {
              const b = outcomeBadge[c.outcome];
              return (
                <button
                  key={c.id}
                  type="button"
                  className={`${s.item} ${openId === c.id ? s.itemActive : ""} ${c.status === "waiting" ? s.itemWaiting : ""}`}
                  onClick={() => setSelectedId(c.id)}
                >
                  <span className={s.itemHead}>
                    <span className={s.itemVisitor}>
                      {c.unread && openId !== c.id && <span className={s.unread} aria-label="Unread" />}
                      {c.visitor}
                    </span>
                    <span className={s.itemTime}>{dayTime(c.last_message_at)}</span>
                  </span>
                  <span className={s.itemPreview}>{c.preview || "—"}</span>
                  <span className={s.itemMeta}>
                    <StatusPill status={c.status} assignedTo={c.assigned_to} since={c.waiting_since} />
                    <span className={`badge ${b.cls}`}>{b.label}</span>
                    {c.message_count} msgs
                  </span>
                </button>
              );
            })}
            {cursor && (
              <div style={{ padding: 12 }}>
                <button type="button" className="btn btn-sm" style={{ width: "100%" }} onClick={fetchMore} disabled={loadMore.busy}>
                  {loadMore.busy ? "Loading…" : "Load more"}
                </button>
              </div>
            )}
          </div>
        </div>

        <div className={s.detail}>
          {openId ? (
            <Transcript key={openId} botId={bot.id} conversationId={openId} onChange={list.reload} />
          ) : (
            <div className="empty" style={{ margin: "auto" }}>
              Select a conversation
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Transcript({ botId, conversationId, onChange }: { botId: string; conversationId: string; onChange: () => void }) {
  const { data: c, error, reload, setData } = useApi(() => api.conversations.get(botId, conversationId), [botId, conversationId]);
  const status = c?.status;

  // Poll for new messages: fast while a person is on the chat.
  useEffect(() => {
    if (!c) return;
    const live = status && LIVE.includes(status);
    const t = setInterval(async () => {
      if (document.hidden) return;
      const after = c.messages[c.messages.length - 1]?.created_at;
      try {
        const u = await api.conversations.updates(botId, conversationId, after);
        if (!u.messages.length && u.status === c.status) return;
        setData((prev) => {
          const base = prev ?? c;
          return merge(base, u.messages, u.status, u.agent?.name ?? base.assigned_to);
        });
        if (u.status !== c.status) onChange();
      } catch {
        /* next tick */
      }
    }, live ? 3000 : 10000);
    return () => clearInterval(t);
  }, [c, status, botId, conversationId, setData, onChange]);

  if (error) return <ErrorState message={error.message} onRetry={reload} />;
  if (!c || c.id !== conversationId) return <Loading />;
  return (
    <TranscriptBody
      c={c}
      botId={botId}
      onReplied={(m) => setData((prev) => merge(prev ?? c, [m], "human", m.author_name ?? c.assigned_to))}
      onStatus={() => {
        reload();
        onChange();
      }}
    />
  );
}

function merge(c: ConversationDetail, incoming: ChatMessage[], status: ChatStatus, assignedTo: string | null): ConversationDetail {
  const ids = new Set(c.messages.map((m) => m.id));
  const fresh = incoming.filter((m) => !ids.has(m.id));
  return {
    ...c,
    status,
    assigned_to: status === "human" ? assignedTo : null,
    messages: fresh.length ? [...c.messages, ...fresh] : c.messages,
  };
}

function needsTeaching(m: ChatMessage): boolean {
  return m.role === "bot" && (m.outcome === "fallback" || m.feedback === "down");
}

function lastVisitorQuestion(c: ConversationDetail): string {
  for (let j = c.messages.length - 1; j >= 0; j--) if (c.messages[j].role === "visitor") return c.messages[j].content;
  return "";
}

const ROLE_LABEL: Record<ChatMessage["role"], string> = { visitor: "Visitor", bot: "Bot", agent: "Agent", system: "" };

function TranscriptBody({
  c,
  botId,
  onReplied,
  onStatus,
}: {
  c: ConversationDetail;
  botId: string;
  onReplied: (m: ChatMessage) => void;
  onStatus: () => void;
}) {
  const { bot } = useBot();
  const canEdit = bot.access_role !== "viewer";
  const b = outcomeBadge[c.outcome];
  const action = useAction();
  const [teachFor, setTeachFor] = useState<string | null>(null);
  const [knowledgeOpen, setKnowledgeOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const live = LIVE.includes(c.status);

  // Keep the newest message in view, unless the reader scrolled up through history.
  useEffect(() => {
    const el = scrollRef.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [c.messages.length, teachFor]);

  const run = (fn: () => Promise<void>) => action.run(fn).then(onStatus);

  const questionBefore = (i: number) => {
    for (let j = i - 1; j >= 0; j--) if (c.messages[j].role === "visitor") return c.messages[j].content;
    return "";
  };

  return (
    <>
      <div className={s.detailHead}>
        <div className={s.detailTitle}>
          <h2>{c.visitor}</h2>
          <span className="mono subtle" style={{ fontSize: 11 }}>
            {c.id.slice(0, 8)}
          </span>
        </div>
        <div className={s.actions}>
          <StatusPill status={c.status} assignedTo={c.assigned_to} since={c.waiting_since} />
          <span className={`badge ${b.cls}`}>{b.label}</span>
          {canEdit && (
            <>
              <span className={s.actionsSep} aria-hidden />
              <button
                type="button"
                className="btn btn-sm"
                aria-pressed={knowledgeOpen}
                title="Turn this chat into an answer or summary, and teach it to this or other bots"
                onClick={() => setKnowledgeOpen((o) => !o)}
              >
                <Icon name="spark" size={13} />
                Save as knowledge
              </button>
              {(!live || c.status === "waiting") && (
                <button type="button" className="btn btn-sm btn-primary" disabled={action.busy} onClick={() => run(() => api.conversations.takeover(botId, c.id))}>
                  <Icon name="conversations" size={13} />
                  {c.status === "waiting" ? "Join chat" : "Take over"}
                </button>
              )}
              {live && (
                <>
                  <button type="button" className="btn btn-sm" disabled={action.busy} onClick={() => run(() => api.conversations.handback(botId, c.id))}>
                    <Icon name="refresh" size={13} />
                    Hand back to bot
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-danger"
                    disabled={action.busy}
                    onClick={() => {
                      if (window.confirm("End this chat? The visitor will be told it has ended.")) void run(() => api.conversations.close(botId, c.id));
                    }}
                  >
                    <Icon name="close" size={13} />
                    End chat
                  </button>
                </>
              )}
            </>
          )}
        </div>
      </div>
      <InlineError message={action.error} />

      {knowledgeOpen && canEdit && (
        <div className={s.knowledgePanel}>
          <TeachForm
            botId={botId}
            conversationId={c.id}
            question={lastVisitorQuestion(c)}
            live={live}
            onDone={(replied) => {
              setKnowledgeOpen(false);
              if (replied) onStatus();
            }}
          />
        </div>
      )}

      {c.status === "waiting" && (
        <div className={s.waitingBanner} role="status">
          <Icon name="help" size={14} />
          This visitor asked for a person {c.waiting_since ? relativeTime(c.waiting_since) : ""}. Reply or press Join chat;
          if nobody joins in about 2 minutes they&apos;ll be asked for their email instead.
        </div>
      )}

      <div className={s.metaStrip}>
        {[
          ["Started", dayTime(c.started_at)],
          ["Duration", duration(c.duration_seconds)],
          ["Page", c.page],
          ["Location", c.location || "—"],
        ].map(([label, value]) => (
          <div key={label} className={s.metaCell}>
            <span className={s.metaLabel}>{label}</span>
            <span className={s.metaValue}>{value}</span>
          </div>
        ))}
      </div>

      {c.handoff_email && (
        <div className={s.handoff}>
          <Icon name="mail" size={14} />
          Lead captured: <span className="mono">{c.handoff_email}</span>
        </div>
      )}

      <div
        className={s.transcript}
        ref={scrollRef}
        onScroll={(e) => {
          const el = e.currentTarget;
          stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
      >
        {c.messages.map((m, i) => {
          if (m.role === "system") {
            return (
              <div key={m.id} className={s.systemMsg}>
                {m.content} · <span className="mono">{clock(m.created_at)}</span>
              </div>
            );
          }
          const prev = c.messages[i - 1];
          const grouped =
            !!prev &&
            prev.role === m.role &&
            (m.role !== "agent" || prev.author_name === m.author_name) &&
            new Date(m.created_at).getTime() - new Date(prev.created_at).getTime() < 60_000 &&
            !(m.role === "bot" && m.outcome && m.outcome !== "answered");
          const name = m.role === "agent" ? m.author_name ?? "Agent" : ROLE_LABEL[m.role];
          const visitor = m.role === "visitor";
          return (
            <div key={m.id} className={`${s.row} ${visitor ? s.rowVisitor : ""} ${grouped ? s.rowGrouped : ""}`}>
              <span className={`${s.avatar} ${m.role === "agent" ? s.avatarAgent : ""} ${grouped ? s.avatarGhost : ""}`} aria-hidden>
                {name.slice(0, 1).toUpperCase()}
              </span>
              <div className={`${s.msg} ${visitor ? s.msgVisitor : ""} ${m.role === "agent" ? s.msgAgent : ""}`}>
                {!grouped && (
                  <span className={s.msgHead}>
                    <span className={s.msgRole}>{name}</span>
                    <span className="mono">{clock(m.created_at)}</span>
                    {m.role === "bot" && m.outcome && m.outcome !== "answered" && (
                      <span className={`badge ${outcomeBadge[m.outcome].cls}`}>{outcomeBadge[m.outcome].label}</span>
                    )}
                  </span>
                )}
                <div className={s.bubble} style={{ whiteSpace: "pre-wrap" }}>
                  {m.content}
                </div>
                {(m.citations.length > 0 || m.feedback) && (
                  <div className={s.citations}>
                    {m.citations.map((cit, k) => (
                      <span key={k} className={s.citation}>
                        <Icon name="file" size={11} />
                        {cit.source_name}
                        {cit.location && <span>{cit.location}</span>}
                      </span>
                    ))}
                    {m.feedback && (
                      <span className={s.feedback} style={{ color: m.feedback === "up" ? "var(--ok)" : "var(--danger-soft)" }}>
                        <Icon name={m.feedback === "up" ? "thumbUp" : "thumbDown"} size={12} />
                        {m.feedback === "up" ? "Helpful" : "Not helpful"}
                      </span>
                    )}
                  </div>
                )}
                {canEdit && (m.role === "agent" || (m.role === "bot" && m.outcome !== "smalltalk")) && (
                  teachFor === m.id ? (
                    <TeachForm
                      botId={botId}
                      conversationId={c.id}
                      question={questionBefore(i)}
                      // A team reply or a good bot reply is the answer to keep; a
                      // fallback or disliked reply is the one to replace.
                      answer={needsTeaching(m) ? "" : m.content}
                      initialMode="answer"
                      live={live}
                      onDone={(replied) => {
                        setTeachFor(null);
                        if (replied) onStatus();
                      }}
                    />
                  ) : (
                    <button
                      type="button"
                      className={`${s.teachBtn} ${needsTeaching(m) ? "" : s.teachBtnQuiet}`}
                      onClick={() => setTeachFor(m.id)}
                    >
                      <Icon name={needsTeaching(m) ? "spark" : "plus"} size={12} />
                      {needsTeaching(m) ? "Teach the right answer" : "Add to knowledge"}
                    </button>
                  )
                )}
              </div>
            </div>
          );
        })}
      </div>

      {canEdit && c.status !== "closed" && <Composer botId={botId} c={c} onSent={onReplied} />}
    </>
  );
}

function Composer({ botId, c, onSent }: { botId: string; c: ConversationDetail; onSent: (m: ChatMessage) => void }) {
  const [text, setText] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);
  const action = useAction();
  const live = LIVE.includes(c.status);

  const send = useCallback(async () => {
    const value = text.trim();
    if (!value) return;
    const m = await action.run(() => api.conversations.reply(botId, c.id, value));
    if (m) {
      setText("");
      if (taRef.current) taRef.current.style.height = "auto";
      onSent(m);
    }
  }, [text, action, botId, c.id, onSent]);

  return (
    <div className={s.composer}>
      <InlineError message={action.error} />
      <div className={s.composerBox}>
        <textarea
          ref={taRef}
          rows={1}
          placeholder={live ? "Reply to the visitor…" : "Reply to take over from the bot…"}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              void send();
            }
          }}
          aria-label="Reply"
        />
        <button type="button" className={s.sendBtn} disabled={action.busy || !text.trim()} onClick={send} aria-label="Send reply">
          <Icon name="send" size={15} />
        </button>
      </div>
      <span className={s.composerHint}>
        {live
          ? "Enter to send · Shift+Enter for a new line. The visitor sees your reply within a few seconds."
          : "Sending pauses the bot until you hand the chat back."}
      </span>
    </div>
  );
}

type KnowledgeMode = "answer" | "summary" | "qa" | "transcript";

const MODES: { key: KnowledgeMode; label: string }[] = [
  { key: "transcript", label: "Whole chat" },
  { key: "answer", label: "Answer" },
  { key: "summary", label: "Summary" },
  { key: "qa", label: "Q&A from chat" },
];

function TeachForm({
  botId,
  conversationId,
  question: initialQuestion,
  answer: initialAnswer = "",
  initialMode = "transcript",
  live,
  onDone,
}: {
  botId: string;
  conversationId: string;
  question: string;
  answer?: string;
  initialMode?: KnowledgeMode;
  live: boolean;
  onDone: (replied: boolean) => void;
}) {
  const { bot } = useBot();
  const [mode, setMode] = useState<KnowledgeMode>(initialMode);
  const [items, setItems] = useState<KnowledgeDraftItem[]>([{ question: initialQuestion, answer: initialAnswer }]);
  // Sending only makes sense for a new answer, not one the visitor already got.
  const [alsoReply, setAlsoReply] = useState(live && !initialAnswer);
  const [targets, setTargets] = useState<string[]>([]);
  const [saved, setSaved] = useState<number | null>(null);
  const action = useAction();
  const drafting = useAction();
  const bots = useApi(() => api.orgs.bots(bot.organization_id), [bot.organization_id]);
  const others = (bots.data ?? []).filter((b) => b.id !== botId);

  const pick = (m: KnowledgeMode) => {
    setMode(m);
    setItems([{ question: m === "answer" ? initialQuestion : "", answer: m === "answer" ? initialAnswer : "" }]);
    drafting.setError(null);
    if (m === "transcript") void draft(m);
  };

  // The whole chat is built without the model, so it loads straight away.
  useEffect(() => {
    if (initialMode === "transcript") void draft("transcript");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const draft = async (m: KnowledgeMode = mode) => {
    const r = await drafting.run(() => api.answers.draft(botId, conversationId, m === "answer" ? "qa" : m));
    if (!r) return;
    if (r.items.length === 0) drafting.setError("Couldn't draft anything from this chat. Write it yourself below.");
    else setItems(r.items);
  };

  const edit = (i: number, patch: Partial<KnowledgeDraftItem>) =>
    setItems((list) => list.map((it, k) => (k === i ? { ...it, ...patch } : it)));

  const toggle = (id: string) => setTargets((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    const r = await action.run(async () => {
      for (const it of items) {
        await api.answers.add(botId, {
          question: it.question,
          answer: it.answer,
          conversation_id: conversationId,
          also_reply: mode === "answer" && alsoReply,
          kind: mode === "summary" ? "summary" : mode === "transcript" ? "conversation" : "answer",
          target_bot_ids: targets,
        });
      }
      return items.length;
    });
    if (r) {
      setSaved(r);
      setTimeout(() => onDone(mode === "answer" && alsoReply), 1800);
    }
  };

  if (saved !== null) {
    return (
      <div className={s.teachForm}>
        <span style={{ color: "var(--ok)", fontSize: 12.5 }}>
          <Icon name="check" size={13} /> Saved to &ldquo;Team answers&rdquo;
          {targets.length > 0 ? ` on this bot and ${targets.length} other${targets.length > 1 ? "s" : ""}` : ""}. Bots use it once
          it finishes indexing.
        </span>
      </div>
    );
  }

  const labelQ = mode === "summary" || mode === "transcript" ? "Title" : "Question";
  const labelA = mode === "summary" ? "Summary" : mode === "transcript" ? "Conversation" : "The right answer";

  return (
    <form className={s.teachForm} onSubmit={save}>
      <div role="group" aria-label="Type of knowledge" className="segmented">
        {MODES.map((m) => (
          <button key={m.key} type="button" aria-pressed={m.key === mode} onClick={() => pick(m.key)}>
            {m.label}
          </button>
        ))}
      </div>

      {mode !== "answer" && (
        <div className={s.draftRow}>
          <span className="subtle" style={{ fontSize: 12 }}>
            {mode === "transcript"
              ? "The full conversation, with emails and phone numbers masked. Remove any other personal details before saving."
              : mode === "summary"
                ? "Drafts a short note without names or emails. Edit it before saving."
                : "Drafts question and answer pairs from the chat. Edit them before saving."}
          </span>
          <button type="button" className="btn btn-sm" onClick={() => draft()} disabled={drafting.busy}>
            <Icon name={mode === "transcript" ? "refresh" : "spark"} size={12} />
            {drafting.busy ? "Drafting…" : mode === "transcript" ? "Reload chat" : items[0].answer ? "Draft again" : "Draft with AI"}
          </button>
        </div>
      )}
      <InlineError message={drafting.error} />

      {items.map((it, i) => (
        <div key={i} className={s.draftItem}>
          <label className="field">
            <span className="field-label">{labelQ}</span>
            <input className="input" value={it.question} onChange={(e) => edit(i, { question: e.target.value })} required minLength={2} />
          </label>
          <label className="field">
            <span className="field-label">{labelA}</span>
            <textarea
              className="textarea"
              rows={mode === "answer" ? 3 : mode === "transcript" ? 10 : 4}
              value={it.answer}
              onChange={(e) => edit(i, { answer: e.target.value })}
              required
              minLength={2}
              placeholder={mode === "answer" ? "Write it the way you'd want the bot to say it." : ""}
              autoFocus={i === 0 && mode === "answer"}
            />
          </label>
          {items.length > 1 && (
            <button type="button" className={s.teachBtn} onClick={() => setItems((list) => list.filter((_, k) => k !== i))}>
              Remove this one
            </button>
          )}
        </div>
      ))}

      {others.length > 0 && (
        <fieldset className={s.dest}>
          <legend className="field-label">Also share with other bots in {bot.organization_name}</legend>
          <label className={s.destRow}>
            <input
              type="checkbox"
              checked={targets.length === others.length}
              onChange={(e) => setTargets(e.target.checked ? others.map((b) => b.id) : [])}
            />
            All bots
          </label>
          {others.map((b) => (
            <label key={b.id} className={s.destRow}>
              <input type="checkbox" checked={targets.includes(b.id)} onChange={() => toggle(b.id)} />
              {b.name}
            </label>
          ))}
          <span className="subtle" style={{ fontSize: 11.5 }}>
            Each bot gets its own copy. Only share notes with no personal details.
          </span>
        </fieldset>
      )}

      {mode === "answer" && (
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5 }}>
          <input type="checkbox" checked={alsoReply} onChange={(e) => setAlsoReply(e.target.checked)} />
          Also send this answer to the visitor now
        </label>
      )}
      <InlineError message={action.error} />
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="btn btn-primary btn-sm" disabled={action.busy || items.some((it) => !it.answer.trim())}>
          {action.busy ? "Saving…" : items.length > 1 ? `Save ${items.length} answers` : "Save"}
        </button>
        <button type="button" className="btn btn-sm" onClick={() => onDone(false)}>
          Cancel
        </button>
      </div>
    </form>
  );
}
