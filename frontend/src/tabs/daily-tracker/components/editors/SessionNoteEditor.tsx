import { useState } from "react";
import type { SessionNote, SessionNoteKind } from "../../types";
import { trackerApi } from "../../api";
import { useLoad, useMutate } from "../../../../shared/useApi";
import Seg from "../../../../shared/ui/Seg";

// Coach & Recap editor: structured items for a coach-session day, not a free
// textarea. Two parts:
// - "Still working on" — EVERY advice item not yet done, across all days
//   (the standing checklist of what the coach wants fixed); tick = absorbed.
// - This day's items (advice 🧑‍🏫 / recap 📋) + a quick-add form.
export default function SessionNoteEditor({
  dateIso,
  items,
  onChanged,
}: {
  dateIso: string;
  items: SessionNote[]; // this day's items (from the loaded week)
  onChanged: () => void; // reload the week; the modal stays open
}) {
  const { data: tags } = useLoad(() => trackerApi.getSessionNoteTags(), []);
  const {
    data: active,
    reload: reloadActive,
  } = useLoad(() => trackerApi.getActiveAdvice(), []);
  const { run, error, busy, clearError } = useMutate();

  const [kind, setKind] = useState<SessionNoteKind>("advice");
  const [draftTags, setDraftTags] = useState<string[]>([]);
  const [text, setText] = useState("");

  const tagLabel = (key: string) =>
    tags?.find((t) => t.key === key)?.label ?? key;

  const refresh = () => {
    onChanged();
    reloadActive();
  };

  const add = async () => {
    if (!text.trim()) return;
    const ok = await run(() =>
      trackerApi.createSessionNote({
        date: dateIso,
        kind,
        tags: draftTags,
        text: text.trim(),
      })
    );
    if (ok === undefined) return; // failed → keep the draft to adjust
    setText("");
    setDraftTags([]);
    refresh();
  };

  const setDone = async (n: SessionNote, done: boolean) => {
    const ok = await run(() =>
      trackerApi.updateSessionNote(n.id, { is_done: done })
    );
    if (ok !== undefined) refresh();
  };

  const remove = async (n: SessionNote) => {
    // DELETE returns 204 (no body) → wrap so success stays truthy for run().
    const ok = await run(async () => {
      await trackerApi.deleteSessionNote(n.id);
      return true;
    });
    if (ok !== undefined) refresh();
  };

  // Advice from OTHER days still open — today's items already render below.
  const carriedAdvice = (active ?? []).filter((n) => n.date !== dateIso);

  return (
    <div className="editor sn-editor">
      {error && (
        <div className="error-banner" onClick={clearError}>
          ⚠ {error}
        </div>
      )}

      {carriedAdvice.length > 0 && (
        <div className="sn-active">
          <div className="sn-block-head">
            Still working on
            <span className="sn-block-sub">
              — advice from earlier sessions; tick when absorbed
            </span>
          </div>
          {carriedAdvice.map((n) => (
            <div key={n.id} className="sn-item">
              <input
                type="checkbox"
                checked={false}
                disabled={busy}
                onChange={() => setDone(n, true)}
                title="Mark as absorbed — removes it from the checklist"
              />
              <span className="sn-date">{n.date.slice(5)}</span>
              <span className="sn-text">{n.text}</span>
              {n.tags.map((t) => (
                <span key={t} className="sn-tag on">
                  {tagLabel(t)}
                </span>
              ))}
            </div>
          ))}
        </div>
      )}

      <div className="sn-block-head">This session</div>
      {items.length === 0 && (
        <p className="editor-sub">
          Nothing noted yet — what did the coach say, which drills did you do?
        </p>
      )}
      {(() => {
        // Drills are numbered by entry order within the day — derived at
        // render time, nothing stored (matches the backend's export).
        let drillNo = 0;
        return items.map((n) => {
          const no = n.kind === "drill" ? ++drillNo : null;
          return (
            <div key={n.id} className="sn-item">
              {n.kind === "advice" ? (
                <input
                  type="checkbox"
                  checked={n.is_done}
                  disabled={busy}
                  onChange={() => setDone(n, !n.is_done)}
                  title="Advice stays on the checklist until ticked"
                />
              ) : (
                <span className="sn-icon">
                  {n.kind === "drill" ? `🏓 ${no}.` : "📋"}
                </span>
              )}
              <span className={`sn-text${n.is_done ? " done" : ""}`}>
                {n.text}
              </span>
              {n.tags.map((t) => (
                <span key={t} className="sn-tag on">
                  {tagLabel(t)}
                </span>
              ))}
              <button
                className="sn-del"
                onClick={() => remove(n)}
                title="Delete this item"
              >
                ✕
              </button>
            </div>
          );
        });
      })()}

      <div className="sn-add">
        <Seg
          options={[
            ["advice", "🧑‍🏫 Coach said"],
            ["drill", "🏓 Drill"],
            ["recap", "📋 Recap"],
          ]}
          value={kind}
          onChange={setKind}
        />
        <div className="sn-tag-row">
          {(tags ?? []).map((t) => {
            const on = draftTags.includes(t.key);
            return (
              <button
                key={t.key}
                className={`sn-tag${on ? " on" : ""}`}
                onClick={() =>
                  setDraftTags((d) =>
                    on ? d.filter((k) => k !== t.key) : [...d, t.key]
                  )
                }
              >
                {t.label}
              </button>
            );
          })}
        </div>
        <div className="sn-input-row">
          <input
            className="sn-input"
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") add();
            }}
            placeholder={
              kind === "advice"
                ? "e.g. stay lower on the FH loop, contact the ball later…"
                : kind === "drill"
                  ? `Drill ${items.filter((n) => n.kind === "drill").length + 1} — e.g. FH topspin vs block, 3 baskets…`
                  : "e.g. solid session, FH felt better in the second hour…"
            }
            autoFocus
          />
          <button
            className="btn primary"
            onClick={add}
            disabled={busy || !text.trim()}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
