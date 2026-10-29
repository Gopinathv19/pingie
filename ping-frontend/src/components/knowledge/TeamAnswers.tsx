"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { useBot } from "@/components/session/BotProvider";
import { InlineError } from "@/components/ui/States";
import { api } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { TeamAnswer } from "@/lib/types";
import { useAction, useApi } from "@/lib/use-api";
import s from "./knowledge.module.css";

/** Answers written by the team for questions the bot couldn't answer,
 *  opened from the "Team answers" row of the sources table. */
export function TeamAnswersDrawer({ onChange, onClose }: { onChange: () => void; onClose: () => void }) {
  const { bot } = useBot();
  const canEdit = bot.access_role !== "viewer";
  const { data, reload } = useApi(() => api.answers.list(bot.id), [bot.id]);
  const [adding, setAdding] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const action = useAction();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const refresh = () => {
    reload();
    onChange();
  };

  const add = async (question: string, answer: string) => {
    if (await action.run(() => api.answers.add(bot.id, { question, answer }))) {
      setAdding(false);
      refresh();
    }
  };

  const save = async (a: TeamAnswer, question: string, answer: string) => {
    if (await action.run(() => api.answers.update(bot.id, a.id, { question, answer }))) {
      setEditingId(null);
      refresh();
    }
  };

  const remove = (a: TeamAnswer) => {
    if (confirm("Delete this answer? The bot will stop using it.")) {
      action.run(() => api.answers.remove(bot.id, a.id)).then(refresh);
    }
  };

  return (
    <div className={s.drawerOverlay} role="dialog" aria-modal="true" aria-label="Team answers" onClick={onClose}>
      <aside className={s.drawer} onClick={(e) => e.stopPropagation()}>
        <header className={s.drawerHead}>
          <div>
            <h2 className={s.drawerTitle}>Team answers{data ? ` (${data.length})` : ""}</h2>
            <span className="field-help" style={{ margin: 0 }}>
              Answers your team wrote for questions the bot couldn&apos;t answer. Add them from a chat with
              &ldquo;Save as knowledge&rdquo;, or here. They&apos;re stored as one &ldquo;Team answers&rdquo; source.
            </span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            {canEdit && !adding && (
              <button type="button" className="btn btn-sm" onClick={() => { setAdding(true); setEditingId(null); }}>
                <Icon name="plus" size={12} />
                Add answer
              </button>
            )}
            <button type="button" className={s.iconBtn} aria-label="Close" onClick={onClose}>
              <Icon name="close" size={14} />
            </button>
          </div>
        </header>

        <div className={s.drawerBody}>
          {adding && <AnswerForm busy={action.busy} submitLabel="Save answer" onSubmit={add} onCancel={() => setAdding(false)} />}
          <InlineError message={action.error} />
          {data?.length === 0 && !adding && <div className="empty" style={{ padding: 12 }}>No team answers yet.</div>}
          {data?.map((a) =>
            editingId === a.id ? (
              <div key={a.id} className={s.answerRow}>
                <AnswerForm
                  initial={a}
                  busy={action.busy}
                  submitLabel="Save changes"
                  onSubmit={(q, ans) => save(a, q, ans)}
                  onCancel={() => setEditingId(null)}
                />
              </div>
            ) : (
              <div key={a.id} className={s.answerRow} style={{ display: "flex", gap: 12 }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13 }}>{a.question}</div>
                  <div style={{ fontSize: 13, color: "var(--text-2)", whiteSpace: "pre-wrap", marginTop: 4 }}>{a.answer}</div>
                  <div className="subtle" style={{ fontSize: 11, marginTop: 4 }}>
                    Added {relativeTime(a.created_at)}
                  </div>
                </div>
                {canEdit && (
                  <div className={s.actions} style={{ alignItems: "flex-start" }}>
                    <button
                      type="button"
                      className={s.iconBtn}
                      aria-label="Edit answer"
                      title="Edit"
                      disabled={action.busy}
                      onClick={() => { setEditingId(a.id); setAdding(false); }}
                    >
                      <Icon name="edit" size={14} />
                    </button>
                    <button
                      type="button"
                      className={s.iconBtn}
                      aria-label="Delete answer"
                      title="Delete"
                      disabled={action.busy}
                      onClick={() => remove(a)}
                    >
                      <Icon name="trash" size={14} />
                    </button>
                  </div>
                )}
              </div>
            ),
          )}
        </div>
      </aside>
    </div>
  );
}

function AnswerForm({
  initial,
  busy,
  submitLabel,
  onSubmit,
  onCancel,
}: {
  initial?: { question: string; answer: string };
  busy: boolean;
  submitLabel: string;
  onSubmit: (question: string, answer: string) => void;
  onCancel: () => void;
}) {
  const [question, setQuestion] = useState(initial?.question ?? "");
  const [answer, setAnswer] = useState(initial?.answer ?? "");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(question, answer);
      }}
      style={{ display: "flex", flexDirection: "column", gap: 8 }}
    >
      <input className="input" placeholder="Question visitors ask" value={question} onChange={(e) => setQuestion(e.target.value)} required minLength={2} />
      <textarea
        className="textarea"
        rows={initial ? Math.min(14, Math.max(4, answer.split("\n").length + 1)) : 3}
        placeholder="The answer the bot should give"
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        required
        minLength={2}
      />
      <div style={{ display: "flex", gap: 8 }}>
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy}>
          {busy ? "Saving…" : submitLabel}
        </button>
        <button type="button" className="btn btn-sm" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}
