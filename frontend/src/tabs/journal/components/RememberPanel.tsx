// The Journal tab's Remember board (user 2026-09-24: "tạo thêm bảng những
// điều cần nhớ, tôi sẽ viết các điều cần ghi nhớ vào đó, để tôi đọc lại hằng
// ngày, và follow. Nó sẽ không bị trôi giống nhật ký") — fills the column
// to the LEFT of the diary. Deliberately not a task list: a memo has no
// status, no date, no daily tick — it just stays, in priority order, until
// edited or deleted. Cards use the diary's markup (Ctrl+B bold, newlines),
// so one card can hold a whole checklist. Every mutation returns the fresh
// list — setData swaps it in (same idiom as the Tracking board).
import { useState } from "react";
import { useLoad, useMutate } from "../../../shared/useApi";
import { trackerApi } from "../../daily-tracker/api";
import type { Memo, MemosOut } from "../../daily-tracker/types";
import RichArea from "../RichArea";
import { renderMarkup } from "../markup";

export default function RememberPanel() {
  const { data, setData } = useLoad(() => trackerApi.getMemos(), []);
  const { run, error, busy, clearError } = useMutate();

  const [draft, setDraft] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editText, setEditText] = useState("");

  const memos = data?.memos ?? [];
  const apply = async (call: () => Promise<MemosOut>) => {
    const out = await run(call);
    if (out !== undefined) setData(out);
  };

  const add = () => {
    if (!draft.trim()) return;
    void apply(() => trackerApi.createMemo(draft.trim()));
    setDraft("");
  };
  const saveEdit = () => {
    if (editingId === null || !editText.trim()) return;
    void apply(() => trackerApi.updateMemo(editingId, editText.trim()));
    setEditingId(null);
  };
  const remove = (m: Memo) => apply(() => trackerApi.deleteMemo(m.id));
  // Move one step up/down: swap in the current order and send the full list.
  const move = (m: Memo, dir: -1 | 1) => {
    const ids = memos.map((x) => x.id);
    const i = ids.indexOf(m.id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    void apply(() => trackerApi.reorderMemos(ids));
  };

  return (
    <aside className="rem-panel">
      <h2 className="rem-head">📌 Remember</h2>
      {error && (
        <div className="error-banner" onClick={clearError}>
          ⚠ {error}
        </div>
      )}

      <section className="rem-block">
        <div className="rem-block-head">
          🧠 Read every day
          <span className="rem-block-sub"> — standing rules, they never scroll away</span>
        </div>

        <div className="rem-add">
          <RichArea
            className="rem-input"
            value={draft}
            onChange={setDraft}
            placeholder="Something to remember and follow…"
          />
          <div className="rem-add-row">
            <span className="rem-hint">Ctrl+B bold · Enter for a new line</span>
            <button className="btn" disabled={busy || !draft.trim()} onClick={add}>
              ＋ Add
            </button>
          </div>
        </div>

        {memos.length === 0 && (
          <p className="rem-empty">
            Nothing pinned yet — write the rules you want to re-read before every session. 📌
          </p>
        )}

        {memos.map((m, i) => (
          <div key={m.id} className="rem-card">
            <span className="rem-num">{i + 1}</span>
            {editingId === m.id ? (
              <div className="rem-edit">
                <RichArea
                  className="rem-input"
                  value={editText}
                  onChange={setEditText}
                  autoFocus
                  onEscape={() => setEditingId(null)}
                />
                <div className="rem-edit-row">
                  <button className="btn" onClick={() => setEditingId(null)}>
                    Cancel
                  </button>
                  <button
                    className="btn primary"
                    disabled={busy || !editText.trim()}
                    onClick={saveEdit}
                  >
                    💾 Save
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="rem-text">{renderMarkup(m.text)}</div>
                <span className="rem-actions">
                  <button
                    className="rem-act"
                    disabled={busy || i === 0}
                    title="Move up (higher priority)"
                    onClick={() => void move(m, -1)}
                  >
                    ↑
                  </button>
                  <button
                    className="rem-act"
                    disabled={busy || i === memos.length - 1}
                    title="Move down"
                    onClick={() => void move(m, 1)}
                  >
                    ↓
                  </button>
                  <button
                    className="rem-act"
                    title="Edit"
                    onClick={() => {
                      setEditingId(m.id);
                      setEditText(m.text);
                    }}
                  >
                    ✏️
                  </button>
                  <button
                    className="rem-act rem-act-del"
                    disabled={busy}
                    title="Delete this memo"
                    onClick={() => void remove(m)}
                  >
                    ✕
                  </button>
                </span>
              </>
            )}
          </div>
        ))}
      </section>
    </aside>
  );
}
