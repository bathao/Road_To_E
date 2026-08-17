// One scouting column (About me / About the opponent): kind-tagged facts
// with add / inline-edit / delete. The "me" column is global knowledge —
// the coach reads it for every opponent and never re-asks it. `intake`
// hosts the column's fixed baseline questionnaire (unanswered items only).
import { useState, type ReactNode } from "react";
import type { Fact, FactKind } from "../types";

const KIND_LABEL: Record<FactKind, string> = {
  strength: "Strength",
  weakness: "Weakness",
  style: "Style",
  note: "Note",
};
const KINDS = Object.keys(KIND_LABEL) as FactKind[];

export default function FactsPanel({
  title,
  hint,
  facts,
  busy,
  intake,
  onAdd,
  onEdit,
  onDelete,
}: {
  title: string;
  hint?: string;
  facts: Fact[];
  busy: boolean;
  intake?: ReactNode;
  onAdd: (kind: FactKind, text: string) => Promise<boolean>;
  onEdit: (id: number, text: string) => Promise<boolean>;
  onDelete: (id: number) => void;
}) {
  const [kind, setKind] = useState<FactKind>("strength");
  const [text, setText] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const add = async () => {
    if (!text.trim()) return;
    if (await onAdd(kind, text.trim())) setText("");
  };
  const saveEdit = async () => {
    if (editingId === null || !editText.trim()) return;
    if (await onEdit(editingId, editText.trim())) setEditingId(null);
  };

  return (
    <div className="tac-facts-col">
      <h3>{title}</h3>
      {hint && <p className="tac-hint">{hint}</p>}
      {intake}
      <ul className="tac-fact-list">
        {facts.length === 0 && <li className="tac-empty">Nothing yet.</li>}
        {facts.map((f) => (
          <li key={f.id} className="tac-fact">
            <span className={`tac-kind tac-kind-${f.kind}`}>
              {KIND_LABEL[f.kind] ?? f.kind}
            </span>
            {editingId === f.id ? (
              <span className="tac-fact-edit">
                <input
                  type="text"
                  className="pb-input"
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void saveEdit();
                    if (e.key === "Escape") setEditingId(null);
                  }}
                  autoFocus
                />
                <button className="btn" disabled={busy} onClick={() => void saveEdit()}>
                  💾
                </button>
                <button className="btn" onClick={() => setEditingId(null)}>
                  ✕
                </button>
              </span>
            ) : (
              <>
                <span
                  className="tac-fact-text"
                  title={
                    f.source === "interview"
                      ? "From an interview answer"
                      : f.source === "intake"
                        ? "From the profile questions"
                        : undefined
                  }
                >
                  {f.text}
                  {f.source === "interview" && <span className="tac-src"> 🎤</span>}
                  {f.source === "intake" && <span className="tac-src"> 📋</span>}
                </span>
                <span className="tac-fact-btns">
                  <button
                    className="icon-btn"
                    title="Edit"
                    onClick={() => {
                      setEditingId(f.id);
                      setEditText(f.text);
                    }}
                  >
                    ✏️
                  </button>
                  <button
                    className="icon-btn danger"
                    title="Delete"
                    onClick={() => onDelete(f.id)}
                  >
                    ✕
                  </button>
                </span>
              </>
            )}
          </li>
        ))}
      </ul>
      <div className="tac-fact-add">
        <select
          className="pb-select"
          value={kind}
          onChange={(e) => setKind(e.target.value as FactKind)}
        >
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {KIND_LABEL[k]}
            </option>
          ))}
        </select>
        <input
          type="text"
          className="pb-input"
          placeholder="Add a fact…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void add();
          }}
        />
        <button className="btn" disabled={busy || !text.trim()} onClick={() => void add()}>
          ＋
        </button>
      </div>
    </div>
  );
}
