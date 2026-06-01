import { useCallback, useEffect, useState } from "react";
import type { Category, MatchIn, WeekResponse } from "./types";
import { trackerApi } from "./api";
import { addDays, mondayOf, toIso } from "./dates";
import WeekNav from "./components/WeekNav";
import WeekGrid from "./components/WeekGrid";
import Modal from "./components/Modal";
import DurationEditor from "./components/editors/DurationEditor";
import MatchEditor from "./components/editors/MatchEditor";
import ChecklistEditor from "./components/editors/ChecklistEditor";
import AnalysisPanel from "./components/AnalysisPanel";

interface EditingCell {
  category: Category;
  dateIso: string;
}

export default function DailyTracker() {
  const [start, setStart] = useState<Date>(() => mondayOf(new Date()));
  const [week, setWeek] = useState<WeekResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditingCell | null>(null);
  // Bumped after every mutation so the AnalysisPanel re-fetches its stats.
  const [dataVersion, setDataVersion] = useState(0);

  const startIso = toIso(start);

  const reload = useCallback(async () => {
    try {
      setError(null);
      const data = await trackerApi.getWeek(startIso);
      setWeek(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [startIso]);

  useEffect(() => {
    void reload();
  }, [reload]);

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

  // ---- export ----
  const endIso = toIso(addDays(start, 6));
  const download = (format: "xlsx" | "csv") => {
    window.open(trackerApi.exportUrl(startIso, endIso, format), "_blank");
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
        <WeekNav
          startIso={startIso}
          endIso={endIso}
          onPrev={() => setStart((s) => addDays(s, -7))}
          onNext={() => setStart((s) => addDays(s, 7))}
          onThisWeek={() => setStart(mondayOf(new Date()))}
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

      <AnalysisPanel reloadSignal={dataVersion} />

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
        </Modal>
      )}
    </div>
  );
}
