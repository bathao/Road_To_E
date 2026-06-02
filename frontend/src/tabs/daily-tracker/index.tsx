import { useCallback, useEffect, useMemo, useState } from "react";
import type { Category, MatchIn, WeekResponse } from "./types";
import { trackerApi } from "./api";
import { fromIso, startOfMonth, toIso } from "./dates";
import type { Mode } from "./period";
import { gridWeekStart, resolveRange, stepAnchor } from "./period";
import PeriodControl from "./components/PeriodControl";
import WeekGrid from "./components/WeekGrid";
import Modal from "./components/Modal";
import DurationEditor from "./components/editors/DurationEditor";
import MatchEditor from "./components/editors/MatchEditor";
import ChecklistEditor from "./components/editors/ChecklistEditor";
import NoteEditor from "./components/editors/NoteEditor";
import AnalysisPanel from "./components/AnalysisPanel";

interface EditingCell {
  category: Category;
  dateIso: string;
}

export default function DailyTracker() {
  // One shared timeline drives both the grid and the Analysis panel.
  const [mode, setMode] = useState<Mode>("week");
  const [anchor, setAnchor] = useState<Date>(() => new Date());
  const [customFrom, setCustomFrom] = useState<string>(() =>
    toIso(startOfMonth(new Date()))
  );
  const [customTo, setCustomTo] = useState<string>(() => toIso(new Date()));

  const [week, setWeek] = useState<WeekResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditingCell | null>(null);
  // Bumped after every mutation so the AnalysisPanel re-fetches its stats.
  const [dataVersion, setDataVersion] = useState(0);

  const period = { mode, anchor, customFrom, customTo };
  const range = useMemo(
    () => resolveRange(period),
    [mode, anchor, customFrom, customTo]
  );
  // The grid always shows a single Mon–Sun week of the shared timeline.
  const gridStartIso = useMemo(
    () => toIso(gridWeekStart(period)),
    [mode, anchor, customFrom, customTo]
  );

  const reload = useCallback(async () => {
    try {
      setError(null);
      setWeek(await trackerApi.getWeek(gridStartIso));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [gridStartIso]);

  useEffect(() => {
    void reload();
  }, [reload]);

  // On first mount, jump the timeline to the most recent day that has data
  // (today is usually empty until it is logged).
  useEffect(() => {
    let alive = true;
    trackerApi
      .getLastDate()
      .then((r) => {
        if (alive && r.date) setAnchor(fromIso(r.date));
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // ---- mutations (all reload the week afterwards) ----
  const afterMutate = async () => {
    await reload();
    setDataVersion((v) => v + 1);
  };

  const saveDuration = async (minutes: number, note: string) => {
    if (!editing) return;
    await trackerApi.upsertActivity({
      date: editing.dateIso,
      category_id: editing.category.id,
      duration_minutes: minutes,
      note: note || null,
    });
    setEditing(null);
    await afterMutate();
  };

  const clearDuration = async () => {
    if (!editing) return;
    await trackerApi.upsertActivity({
      date: editing.dateIso,
      category_id: editing.category.id,
      duration_minutes: 0,
      note: null,
    });
    setEditing(null);
    await afterMutate();
  };

  const addMatch = async (payload: Omit<MatchIn, "date" | "category_id">) => {
    if (!editing) return;
    await trackerApi.createMatch({
      date: editing.dateIso,
      category_id: editing.category.id,
      ...payload,
    });
    await afterMutate();
  };

  const deleteMatch = async (id: number) => {
    await trackerApi.deleteMatch(id);
    await afterMutate();
  };

  const savePhysicalChecks = async (items: string[]) => {
    if (!editing) return;
    await trackerApi.setPhysicalChecks(editing.dateIso, items);
    setEditing(null);
    await afterMutate();
  };

  const saveNote = async (text: string) => {
    if (!editing) return;
    await trackerApi.setDayNote(editing.dateIso, text);
    setEditing(null);
    await afterMutate();
  };

  // ---- export (the currently selected range) ----
  const download = (format: "xlsx" | "csv") => {
    window.open(
      trackerApi.exportUrl(range.fromIso, range.toIso, format),
      "_blank"
    );
  };

  // ---- editor selection ----
  const editingMatches =
    editing && week
      ? week.matches.filter(
          (m) =>
            m.category_id === editing.category.id && m.date === editing.dateIso
        )
      : [];
  const editingActivity =
    editing && week
      ? week.activities.find(
          (a) =>
            a.category_id === editing.category.id && a.date === editing.dateIso
        )
      : undefined;
  const editingChecks =
    editing && week ? week.physical_checks[editing.dateIso] ?? [] : [];

  return (
    <div className="daily-tracker">
      <div className="toolbar">
        <PeriodControl
          mode={mode}
          label={range.label}
          customFrom={customFrom}
          customTo={customTo}
          onMode={setMode}
          onStep={(dir) => setAnchor((a) => stepAnchor(mode, a, dir))}
          onToday={() => setAnchor(new Date())}
          onCustomFrom={setCustomFrom}
          onCustomTo={setCustomTo}
        />
        <div className="export-btns">
          <button className="btn" onClick={() => download("xlsx")}>
            ⬇ Excel
          </button>
          <button className="btn" onClick={() => download("csv")}>
            ⬇ CSV
          </button>
        </div>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {week ? (
        <WeekGrid
          week={week}
          onCellClick={(category, dateIso) => setEditing({ category, dateIso })}
        />
      ) : (
        !error && <div className="loading">Loading…</div>
      )}

      <AnalysisPanel
        mode={mode}
        fromIso={range.fromIso}
        toIso={range.toIso}
        label={range.label}
        reloadSignal={dataVersion}
      />

      {editing && (
        <Modal
          title={`${editing.category.label} · ${editing.dateIso}`}
          onClose={() => setEditing(null)}
        >
          {editing.category.type === "duration" && (
            <DurationEditor
              category={editing.category}
              current={editingActivity}
              onSave={saveDuration}
              onClear={clearDuration}
            />
          )}
          {editing.category.type === "match" && (
            <MatchEditor
              category={editing.category}
              matches={editingMatches}
              onAdd={addMatch}
              onDelete={deleteMatch}
            />
          )}
          {editing.category.type === "checklist" && (
            <ChecklistEditor
              category={editing.category}
              checked={editingChecks}
              onSave={savePhysicalChecks}
            />
          )}
          {editing.category.type === "note" && (
            <NoteEditor
              current={editing && week ? week.day_notes[editing.dateIso] ?? "" : ""}
              onSave={saveNote}
            />
          )}
        </Modal>
      )}
    </div>
  );
}
