"use client";

import { useState } from "react";
import { ErrorState, InlineError, Loading } from "@/components/ui/States";
import { api } from "@/lib/api";
import type { SavedReply } from "@/lib/types";
import { useAction, useApi } from "@/lib/use-api";
import s from "./settings.module.css";

/** Canned replies agents insert in live chat by typing "/" in the reply box. Saved immediately. */
export function SavedReplies({ botId, canEdit }: { botId: string; canEdit: boolean }) {
  const list = useApi(() => api.savedReplies.list(botId), [botId]);
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const action = useAction();

  const open = (r: SavedReply | null) => {
    setEditing(r ? r.id : "new");
    setTitle(r?.title ?? "");
    setBody(r?.body ?? "");
    action.setError(null);
  };
  const save = () =>
    action
      .run(async () => {
        if (editing === "new") await api.savedReplies.add(botId, { title, body });
        else if (editing) await api.savedReplies.update(botId, editing, { title, body });
        setEditing(null);
      })
      .then(list.reload);
  const remove = (r: SavedReply) => {
    if (!window.confirm(`Delete the saved reply "${r.title}"?`)) return;
    void action.run(() => api.savedReplies.remove(botId, r.id)).then(list.reload);
  };

  const form = (
    <div className={s.replyForm}>
      <input className="input" placeholder="Title, e.g. Refund policy" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={120} autoFocus />
      <textarea className="textarea" rows={3} placeholder="The reply your team sends" value={body} onChange={(e) => setBody(e.target.value)} maxLength={4000} />
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" className="btn btn-primary btn-sm" disabled={action.busy || !title.trim() || !body.trim()} onClick={save}>
          {action.busy ? "Saving…" : "Save reply"}
        </button>
        <button type="button" className="btn btn-sm" onClick={() => setEditing(null)}>
          Cancel
        </button>
      </div>
    </div>
  );

  if (list.error) return <ErrorState message={list.error.message} onRetry={list.reload} />;
  if (!list.data) return <Loading />;
  return (
    <div className="panel-body" style={{ maxWidth: 760 }}>
      <span className="field-help">
        In a conversation, type <span className="mono">/</span> in the reply box to insert one. Changes here save right away.
      </span>
      {list.data.length === 0 && editing !== "new" && <div className="empty">No saved replies yet.</div>}
      <div className={s.replies}>
        {list.data.map((r) =>
          editing === r.id ? (
            <div key={r.id}>{form}</div>
          ) : (
            <div key={r.id} className={s.replyRow}>
              <span className={s.replyText}>
                <strong>{r.title}</strong>
                <span className="subtle">{r.body}</span>
              </span>
              {canEdit && (
                <span style={{ display: "flex", gap: 6 }}>
                  <button type="button" className="btn btn-sm" onClick={() => open(r)}>
                    Edit
                  </button>
                  <button type="button" className="btn btn-sm" onClick={() => remove(r)}>
                    Delete
                  </button>
                </span>
              )}
            </div>
          ),
        )}
      </div>
      {editing === "new" && form}
      {canEdit && editing === null && (
        <button type="button" className="btn btn-sm" style={{ alignSelf: "flex-start" }} onClick={() => open(null)}>
          Add a saved reply
        </button>
      )}
      <InlineError message={action.error} />
    </div>
  );
}
