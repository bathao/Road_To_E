// The fixed baseline questionnaire for one scouting column. Renders ONLY the
// still-unanswered intake keys (answered ones live in the fact list below,
// editable/deletable like any fact — deleting one brings its question back).
// Choice items save on tap; text items save on Enter/＋; `unsure` items add
// "Not sure…" → pick a leaning or "No idea" (an honest answer that still
// fills the slot). All questions answered → the card disappears for good.
import { useState } from "react";
import type { IntakeItem } from "../intake";
import { intakeFactText, intakeUnsureText } from "../intake";
import type { Fact } from "../types";

export default function IntakeCard({
  items,
  facts,
  busy,
  onAnswer,
}: {
  items: IntakeItem[];
  facts: Fact[];
  busy: boolean;
  onAnswer: (item: IntakeItem, text: string) => Promise<boolean>;
}) {
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  // Keys currently in "Not sure…" mode (choices re-offered as leanings).
  const [unsureKeys, setUnsureKeys] = useState<Set<string>>(new Set());

  const answered = new Set(facts.map((f) => f.key).filter(Boolean));
  const missing = items.filter((i) => !answered.has(i.key));
  if (missing.length === 0) return null;

  const saveText = async (item: IntakeItem) => {
    const typed = (drafts[item.key] ?? "").trim();
    if (!typed) return;
    if (await onAnswer(item, intakeFactText(item, typed)))
      setDrafts((d) => ({ ...d, [item.key]: "" }));
  };
  const setUnsure = (key: string, on: boolean) =>
    setUnsureKeys((s) => {
      const next = new Set(s);
      if (on) next.add(key);
      else next.delete(key);
      return next;
    });

  return (
    <div className="tac-intake">
      <div className="tac-intake-head">
        <span className="tac-intake-title">📋 Profile questions</span>
        <span className="tac-intake-count">
          {items.length - missing.length}/{items.length} answered
        </span>
      </div>
      {missing.map((item) => (
        <div key={item.key} className="tac-intake-item">
          <span className="tac-intake-label">{item.label}</span>
          {item.choices && unsureKeys.has(item.key) ? (
            <span className="tac-intake-choices">
              <span className="tac-intake-leaning">Leaning:</span>
              {item.choices.map((c) => (
                <button
                  key={c.en}
                  className="btn tac-chip"
                  disabled={busy}
                  onClick={() => void onAnswer(item, intakeUnsureText(item, c))}
                >
                  ≈ {c.en}
                </button>
              ))}
              <button
                className="btn tac-chip"
                disabled={busy}
                onClick={() => void onAnswer(item, intakeUnsureText(item))}
              >
                No idea
              </button>
              <button
                className="btn tac-chip"
                title="Back to the definite choices"
                onClick={() => setUnsure(item.key, false)}
              >
                ✕
              </button>
            </span>
          ) : item.choices ? (
            <span className="tac-intake-choices">
              {item.choices.map((c) => (
                <button
                  key={c.en}
                  className="btn tac-chip"
                  disabled={busy}
                  onClick={() => void onAnswer(item, intakeFactText(item, c))}
                >
                  {c.en}
                </button>
              ))}
              {item.unsure && (
                <button
                  className="btn tac-chip tac-chip-muted"
                  disabled={busy}
                  onClick={() => setUnsure(item.key, true)}
                >
                  Not sure…
                </button>
              )}
            </span>
          ) : (
            <span className="tac-intake-text">
              <input
                type="text"
                className="pb-input"
                placeholder={item.placeholder}
                value={drafts[item.key] ?? ""}
                onChange={(e) =>
                  setDrafts((d) => ({ ...d, [item.key]: e.target.value }))
                }
                onKeyDown={(e) => {
                  if (e.key === "Enter") void saveText(item);
                }}
              />
              <button
                className="btn"
                disabled={busy || !(drafts[item.key] ?? "").trim()}
                onClick={() => void saveText(item)}
              >
                ＋
              </button>
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
