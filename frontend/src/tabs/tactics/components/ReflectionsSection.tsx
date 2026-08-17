// "My analysis" — the user's own post-match tactical read on this opponent.
// Free-form and subjective by design (facts stay one-line conclusions); the
// coach synthesizes these into the next plan and cross-checks them against
// the H2H data. The iterate loop: write a note → Regenerate the plan →
// answer its data_gaps → repeat.
import { useState } from "react";
import type { Reflection } from "../types";

export default function ReflectionsSection({
  opponentName,
  reflections,
  busy,
  onAdd,
  onEdit,
  onDelete,
}: {
  opponentName: string;
  reflections: Reflection[];
  busy: boolean;
  onAdd: (text: string) => Promise<boolean>;
  onEdit: (id: number, text: string) => Promise<boolean>;
  onDelete: (id: number) => void;
}) {
  const [draft, setDraft] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const add = async () => {
    if (!draft.trim()) return;
    if (await onAdd(draft.trim())) setDraft("");
  };
  const saveEdit = async () => {
    if (editingId === null || !editText.trim()) return;
    if (await onEdit(editingId, editText.trim())) setEditingId(null);
  };

  return (
    <section className="tac-reflections">
      <div className="tac-sec-head">
        <h2>📝 My analysis</h2>
      </div>
      <p className="tac-hint">
        Your own read on the matches against {opponentName} — what you felt,
        saw, tried. Subjective is fine: the coach cross-checks it against the
        data. Add a note, then regenerate the plan.
      </p>
      <div className="tac-reflect-add">
        <textarea
          className="pb-input tac-reflect-input"
          rows={3}
          placeholder={`What did you notice playing ${opponentName}?`}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button
          className="btn primary"
          disabled={busy || !draft.trim()}
          onClick={() => void add()}
        >
          ＋ Add note
        </button>
      </div>
      <ul className="tac-reflect-list">
        {reflections.map((r) => (
          <li key={r.id} className="tac-reflect">
            <span className="tac-reflect-date">
              {r.created_at ? r.created_at.slice(0, 10) : ""}
            </span>
            {editingId === r.id ? (
              <span className="tac-reflect-edit">
                <textarea
                  className="pb-input tac-reflect-input"
                  rows={3}
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  autoFocus
                />
                <span className="tac-reflect-btns">
                  <button className="btn" disabled={busy} onClick={() => void saveEdit()}>
                    💾
                  </button>
                  <button className="btn" onClick={() => setEditingId(null)}>
                    ✕
                  </button>
                </span>
              </span>
            ) : (
              <>
                <span className="tac-reflect-text">{r.text}</span>
                <span className="tac-reflect-btns">
                  <button
                    className="icon-btn"
                    title="Edit"
                    onClick={() => {
                      setEditingId(r.id);
                      setEditText(r.text);
                    }}
                  >
                    ✏️
                  </button>
                  <button
                    className="icon-btn danger"
                    title="Delete"
                    onClick={() => onDelete(r.id)}
                  >
                    ✕
                  </button>
                </span>
              </>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
