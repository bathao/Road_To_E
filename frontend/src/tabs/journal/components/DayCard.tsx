// One timeline row: a Day One-style date block (weekday + big day number)
// on the left, the day's entry card on the right. Three groups mirroring
// the composer 1:1: 🧑‍🏫 Lesson (💬 coach said / drills numbered / 📋 recap),
// 🏓 Matches (per-opponent notes), 📝 Notes. Everything is plain diary
// content (no checklist lifecycle — dropped 2026-08-21). Edit / delete
// reveal on hover; mutations ride the shared APIs and the parent refreshes
// every list after a change.
import { useState } from "react";
import { trackerApi } from "../../daily-tracker/api";
import type { JournalDay, JournalMatch, SessionNote } from "../../daily-tracker/types";
import { useMutate } from "../../../shared/useApi";
import { formatHotkeys, renderMarkup } from "../markup";

export default function DayCard({
  day,
  todayIso,
  tagLabel,
  onChanged,
}: {
  day: JournalDay;
  todayIso: string;
  tagLabel: (key: string) => string;
  onChanged: () => void;
}) {
  const { run, error, busy, clearError } = useMutate();
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");
  // Match notes edit in place too (user 2026-08-21: "đều sửa trên timeline
  // được hết, cho nó đồng bộ") — separate state: match ids ≠ note ids.
  const [editingMatchId, setEditingMatchId] = useState<number | null>(null);
  const [matchText, setMatchText] = useState("");

  const saveEdit = async () => {
    if (editingId === null || !editText.trim()) return;
    const ok = await run(() =>
      trackerApi.updateSessionNote(editingId, { text: editText.trim() })
    );
    if (ok !== undefined) {
      setEditingId(null);
      onChanged();
    }
  };
  const remove = async (n: SessionNote) => {
    // DELETE returns 204 (no body) → wrap so success stays truthy for run().
    const ok = await run(async () => {
      await trackerApi.deleteSessionNote(n.id);
      return true;
    });
    if (ok !== undefined) onChanged();
  };
  const saveMatchEdit = async () => {
    if (editingMatchId === null || !matchText.trim()) return;
    const ok = await run(() =>
      trackerApi.setMatchNote(editingMatchId, matchText.trim())
    );
    if (ok !== undefined) {
      setEditingMatchId(null);
      onChanged();
    }
  };
  const clearMatchNote = async (m: JournalMatch) => {
    // Blank PATCH clears tracker_match.note — the match itself is untouched.
    const ok = await run(() => trackerApi.setMatchNote(m.id, ""));
    if (ok !== undefined) onChanged();
  };

  const date = new Date(day.date + "T00:00:00");
  const dow = date.toLocaleDateString("en-GB", { weekday: "short" });
  const dom = day.date.slice(8, 10);

  const coachItems = day.items.filter((n) => n.kind !== "lesson");
  const lessons = day.items.filter((n) => n.kind === "lesson");
  let drillNo = 0;

  const renderItem = (n: SessionNote) => {
    const no = n.kind === "drill" ? ++drillNo : null;
    return (
      <div key={n.id} className="jr-item">
        <span className="jr-item-icon">
          {n.kind === "advice"
            ? "💬"
            : n.kind === "drill"
              ? `${no}.`
              : n.kind === "recap"
                ? "📋"
                : "📝"}
        </span>
        {editingId === n.id ? (
          <span className="jr-edit-block">
            <textarea
              className="jr-input jr-edit-area"
              rows={Math.min(14, Math.max(4, editText.split("\n").length + 1))}
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              onKeyDown={(e) => {
                if (formatHotkeys(e, setEditText)) return;
                if (e.key === "Escape") setEditingId(null);
              }}
              autoFocus
            />
            <span className="jr-edit-actions">
              <button className="btn" onClick={() => setEditingId(null)}>
                Cancel
              </button>
              <button
                className="btn primary"
                disabled={busy}
                onClick={() => void saveEdit()}
              >
                💾 Save
              </button>
            </span>
          </span>
        ) : (
          <>
            <span className="jr-item-text">
              {renderMarkup(n.text)}
              {n.tags.map((t) => (
                <span key={t} className="jr-tag">
                  {tagLabel(t)}
                </span>
              ))}
            </span>
            <span className="jr-item-actions">
              <button
                className="jr-act"
                title="Edit"
                onClick={() => {
                  setEditingId(n.id);
                  setEditText(n.text);
                }}
              >
                ✏️
              </button>
              <button
                className="jr-act jr-act-del"
                title="Delete"
                onClick={() => void remove(n)}
              >
                ✕
              </button>
            </span>
          </>
        )}
      </div>
    );
  };

  return (
    <div className="jr-row">
      <div className={`jr-datebox${day.date === todayIso ? " today" : ""}`}>
        <span className="jr-dow">{dow}</span>
        <span className="jr-dom">{dom}</span>
      </div>
      <div className="jr-card">
        {error && (
          <div className="error-banner" onClick={clearError}>
            ⚠ {error}
          </div>
        )}
        {coachItems.length > 0 && (
          <div className="jr-group">
            <div className="jr-group-head">
              {/* User-requested Vietnamese title (2026-08-21) — "Coach" before
                  the name out of respect; exception to the English-GUI rule. */}
              🧑‍🏫 {day.coaches.length > 0
                ? `Tập với Coach ${day.coaches.join(" + Coach ")}`
                : "Tập với Coach"}
            </div>
            {coachItems.map(renderItem)}
          </div>
        )}
        {day.matches.length > 0 && (
          <div className="jr-group">
            <div className="jr-group-head">🏓 Matches</div>
            {day.matches.map((m) => (
              <div key={m.id} className="jr-match">
                <div className="jr-match-head">
                  <div className="jr-match-label">{m.label}</div>
                  {editingMatchId !== m.id && (
                    <span className="jr-item-actions">
                      <button
                        className="jr-act"
                        title="Edit"
                        onClick={() => {
                          setEditingMatchId(m.id);
                          setMatchText(m.note);
                        }}
                      >
                        ✏️
                      </button>
                      <button
                        className="jr-act jr-act-del"
                        title="Clear this note (the match stays)"
                        onClick={() => void clearMatchNote(m)}
                      >
                        ✕
                      </button>
                    </span>
                  )}
                </div>
                {editingMatchId === m.id ? (
                  <span className="jr-edit-block">
                    <textarea
                      className="jr-input jr-edit-area"
                      rows={Math.min(14, Math.max(4, matchText.split("\n").length + 1))}
                      value={matchText}
                      onChange={(e) => setMatchText(e.target.value)}
                      onKeyDown={(e) => {
                        if (formatHotkeys(e, setMatchText)) return;
                        if (e.key === "Escape") setEditingMatchId(null);
                      }}
                      autoFocus
                    />
                    <span className="jr-edit-actions">
                      <button className="btn" onClick={() => setEditingMatchId(null)}>
                        Cancel
                      </button>
                      <button
                        className="btn primary"
                        disabled={busy}
                        onClick={() => void saveMatchEdit()}
                      >
                        💾 Save
                      </button>
                    </span>
                  </span>
                ) : (
                  <div className="jr-item-text">{renderMarkup(m.note)}</div>
                )}
              </div>
            ))}
          </div>
        )}
        {lessons.length > 0 && (
          <div className="jr-group">
            <div className="jr-group-head">📝 Notes</div>
            {lessons.map(renderItem)}
          </div>
        )}
      </div>
    </div>
  );
}
