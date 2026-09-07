// The Journal tab's Tracking board (user 2026-08-24: "kiểu giống JIRA,
// assign task cho tôi làm... task HLV giao, tôi phải follow daily") — fills
// the column to the right of the diary. Two blocks:
//   1. Today's dailies — daily tasks not ticked yet today (tick in place;
//      streak 🔥 counts consecutive practiced days).
//   2. The board — To Do / Doing with status moves, quick-add, Done
//      collapsed (server keeps done tasks listed for 7 days).
// The "ai" task source stays valid in the backend, but the UI dropped it
// (user 2026-08-24: AI-coach tasks not sensible yet) — sources are coach/self.
// Every task mutation returns the fresh list — setData swaps it in.
import { useState } from "react";
import { useLoad, useMutate } from "../../../shared/useApi";
import { toIso } from "../../../shared/dates";
import Seg from "../../../shared/ui/Seg";
import { trackerApi } from "../../daily-tracker/api";
import type { Task, TasksOut, TaskSource, TaskStatus } from "../../daily-tracker/types";
import { renderMarkup } from "../markup";

const SOURCE_ICON: Record<TaskSource, string> = {
  coach: "🧑‍🏫",
  ai: "🤖",
  self: "📝",
};
const SOURCE_TITLE: Record<TaskSource, string> = {
  coach: "Assigned by the real-life coach",
  ai: "Suggested by the AI coach",
  self: "Self-assigned",
};

function StreakChip({ t }: { t: Task }) {
  if (!t.is_daily || t.streak === 0) return null;
  return (
    <span className="trk-streak" title={`${t.streak} consecutive days`}>
      🔥 {t.streak}d
    </span>
  );
}

export default function TrackingPanel() {
  const todayIso = toIso(new Date());
  const { data, setData } = useLoad(() => trackerApi.getTasks(), []);
  const { run, error, busy, clearError } = useMutate();

  const [title, setTitle] = useState("");
  const [source, setSource] = useState<TaskSource>("coach");
  const [isDaily, setIsDaily] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");

  const tasks = data?.tasks ?? [];
  // The server returns the fresh list from every mutation — swap it in.
  const apply = async (call: () => Promise<TasksOut>) => {
    const out = await run(call);
    if (out !== undefined) setData(out);
  };

  const add = () => {
    if (!title.trim()) return;
    void apply(() =>
      trackerApi.createTask({ title: title.trim(), source, is_daily: isDaily })
    );
    setTitle("");
  };
  const move = (t: Task, status: TaskStatus) =>
    apply(() => trackerApi.updateTask(t.id, { status }));
  const saveTitle = () => {
    if (editingId === null || !editTitle.trim()) return;
    void apply(() =>
      trackerApi.updateTask(editingId, { title: editTitle.trim() })
    );
    setEditingId(null);
  };
  const tick = (t: Task, checked: boolean) =>
    apply(() => trackerApi.checkTask(t.id, todayIso, checked));

  const dailiesDue = tasks.filter(
    (t) => t.is_daily && t.status !== "done" && !t.checked_today
  );
  const board: [TaskStatus, string, Task[]][] = (
    [
      ["todo", "To Do", tasks.filter((t) => t.status === "todo")],
      ["doing", "Doing", tasks.filter((t) => t.status === "doing")],
    ] as [TaskStatus, string, Task[]][]
  ).filter(([, , list]) => list.length > 0);
  const done = tasks.filter((t) => t.status === "done");

  const card = (t: Task) => (
    <div key={t.id} className="trk-card">
      {t.is_daily && (
        <input
          type="checkbox"
          className="trk-tick"
          checked={t.checked_today}
          disabled={busy}
          title={t.checked_today ? "Done today — click to un-tick" : "Did it today?"}
          onChange={() => void tick(t, !t.checked_today)}
        />
      )}
      {editingId === t.id ? (
        <span className="trk-edit">
          <input
            className="jr-input"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveTitle();
              if (e.key === "Escape") setEditingId(null);
            }}
            autoFocus
          />
          <button className="btn" disabled={busy} onClick={saveTitle}>
            💾
          </button>
        </span>
      ) : (
        <span className="trk-body">
          <span className="trk-title">
            <span className="trk-src" title={SOURCE_TITLE[t.source]}>
              {SOURCE_ICON[t.source]}
            </span>{" "}
            {renderMarkup(t.title)}
            <StreakChip t={t} />
          </span>
          <span className="trk-actions">
            {t.status === "todo" && (
              <button
                className="trk-act"
                disabled={busy}
                title="Start — move to Doing"
                onClick={() => void move(t, "doing")}
              >
                ▶
              </button>
            )}
            {t.status === "doing" && (
              <button
                className="trk-act"
                disabled={busy}
                title="Back to To Do"
                onClick={() => void move(t, "todo")}
              >
                ⏸
              </button>
            )}
            {t.status !== "done" ? (
              <button
                className="trk-act"
                disabled={busy}
                title="Complete — leaves the board after a week"
                onClick={() => void move(t, "done")}
              >
                ✔
              </button>
            ) : (
              <button
                className="trk-act"
                disabled={busy}
                title="Reopen"
                onClick={() => void move(t, "todo")}
              >
                ↩
              </button>
            )}
            <button
              className="trk-act"
              title="Edit"
              onClick={() => {
                setEditingId(t.id);
                setEditTitle(t.title);
              }}
            >
              ✏️
            </button>
            <button
              className="trk-act trk-act-del"
              disabled={busy}
              title="Delete task (its daily history goes too)"
              onClick={() => void apply(() => trackerApi.deleteTask(t.id))}
            >
              ✕
            </button>
          </span>
        </span>
      )}
    </div>
  );

  return (
    <aside className="trk-panel">
      <h2 className="trk-head">🎯 Tracking</h2>
      {error && (
        <div className="error-banner" onClick={clearError}>
          ⚠ {error}
        </div>
      )}

      {dailiesDue.length > 0 && (
        <section className="trk-block trk-due">
          <div className="trk-block-head">
            ☀️ Today
            <span className="trk-block-sub"> — dailies not done yet</span>
          </div>
          {dailiesDue.map(card)}
        </section>
      )}

      <section className="trk-block">
        <div className="trk-block-head">
          📋 Board
          <span className="trk-block-sub"> — the coach reads all of it</span>
        </div>
        <div className="trk-add">
          <input
            className="jr-input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") add();
            }}
            placeholder="New task…"
          />
          <div className="trk-add-row">
            <Seg
              options={[
                ["coach", "🧑‍🏫 Coach"],
                ["self", "📝 Me"],
              ]}
              value={source}
              onChange={setSource}
            />
            <label className="trk-daily-toggle" title="Repeats — tick it every day you do it; keeps a streak">
              <input
                type="checkbox"
                checked={isDaily}
                onChange={(e) => setIsDaily(e.target.checked)}
              />
              daily
            </label>
            <button className="btn" disabled={busy || !title.trim()} onClick={add}>
              ＋ Add
            </button>
          </div>
        </div>
        {tasks.length === 0 && (
          <p className="trk-empty">
            Nothing tracked yet — add what the coach asked you to work on. ✍️
          </p>
        )}
        {board.map(([status, label, list]) => (
          <div key={status} className="trk-group">
            <div className="trk-group-head">
              {label} <span className="trk-count">{list.length}</span>
            </div>
            {list.map(card)}
          </div>
        ))}
        {done.length > 0 && (
          <details className="trk-done">
            <summary>
              Done <span className="trk-count">{done.length}</span>
              <span className="trk-block-sub"> — last 7 days</span>
            </summary>
            {done.map(card)}
          </details>
        )}
      </section>
    </aside>
  );
}
