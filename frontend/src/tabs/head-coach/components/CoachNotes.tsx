// The coach's notebook: durable facts (goals, deadlines, constraints) that
// get injected into every chat reply AND every weekly verdict. Entries are
// auto-written by the coach after chat exchanges; the player can add or
// remove entries by hand.
import { useState } from "react";
import type { CoachNote } from "../types";
import { fmtChatTime } from "../fmt";

export default function CoachNotes({
  notes,
  onAdd,
  onDelete,
  busy,
  error,
}: {
  notes: CoachNote[];
  // Resolves true on success — the input is only cleared then, so a failed
  // save doesn't silently discard what was typed.
  onAdd: (text: string) => Promise<boolean>;
  onDelete: (id: number) => Promise<void>;
  busy: boolean;
  error?: string | null;
}) {
  const [text, setText] = useState("");

  const add = async () => {
    const t = text.trim();
    if (!t || busy) return;
    if (await onAdd(t)) setText("");
  };

  return (
    <div className="hc-notes">
      {error && <div className="hc-error">⚠️ {error}</div>}
      {notes.length === 0 && (
        <div className="hc-notes-empty">
          The notebook is empty. The coach will record important goals,
          deadlines and constraints after each exchange — you can also add
          your own.
        </div>
      )}
      <ul className="hc-notes-list">
        {notes.map((n) => (
          <li key={n.id} className="hc-note">
            <div className="hc-note-text">{n.text}</div>
            <div className="hc-note-meta">
              <span>{fmtChatTime(n.created_at)}</span>
              <span className="hc-chip">{n.source === "user" ? "added by you" : "added by coach"}</span>
              <button
                className="hc-note-del"
                title="Delete note"
                onClick={() => {
                  if (window.confirm("Delete this note from the coach's notebook?")) {
                    void onDelete(n.id);
                  }
                }}
              >
                ✕
              </button>
            </div>
          </li>
        ))}
      </ul>
      <div className="hc-notes-input">
        <input
          type="text"
          value={text}
          maxLength={500}
          placeholder="Add your own note to the notebook…"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void add();
          }}
        />
        <button className="btn" onClick={add} disabled={busy || !text.trim()}>
          Add
        </button>
      </div>
    </div>
  );
}
