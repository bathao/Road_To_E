import { useCallback, useEffect, useMemo, useState } from "react";
import type { Category, MatchIn, WeekResponse } from "./types";
import { trackerApi } from "./api";
import { fromIso, startOfMonth, toIso } from "../../shared/dates";
import type { Mode } from "../../shared/period";
import { resolveRange, stepAnchor } from "../../shared/period";
import PeriodControl from "../../shared/ui/PeriodControl";
import WeekGrid from "./components/WeekGrid";
import Modal from "../../shared/ui/Modal";
import DurationEditor from "./components/editors/DurationEditor";
import MatchEditor from "./components/editors/MatchEditor";
import ChecklistEditor from "./components/editors/ChecklistEditor";
import NoteEditor from "./components/editors/NoteEditor";
import AnalysisPanel from "./components/AnalysisPanel";
import { trainingApi } from "../training-center/api";
import SessionCard from "../training-center/components/SessionCard";
import type { TrainingSession } from "../training-center/types";

interface EditingCell {
  category: Category;
  dateIso: string;
}

export default function DailyTracker() {
  // One shared timeline drives both the grid and the Analysis panel.
  const [mode, setMode] = useState<Mode>("month");
  const [anchor, setAnchor] = useState<Date>(() => new Date());
  const [customFrom, setCustomFrom] = useState<string>(() =>
    toIso(startOfMonth(new Date()))
  );
  const [customTo, setCustomTo] = useState<string>(() => toIso(new Date()));

  const [week, setWeek] = useState<WeekResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<EditingCell | null>(null);
  // Read-only Training Center session shown when a mirrored Physical cell is clicked.
  const [viewSession, setViewSession] = useState<TrainingSession | null>(null);
  // Bumped after every mutation so the AnalysisPanel re-fetches its stats.
  const [dataVersion, setDataVersion] = useState(0);
  // Measured width of the grid's Category column; the Analysis chart uses it as
  // a left gutter so its day points line up under the grid's day columns.
  const [gridGutter, setGridGutter] = useState(210);

  const period = { mode, anchor, customFrom, customTo };
  const range = useMemo(
    () => resolveRange(period),
    [mode, anchor, customFrom, customTo]
  );
  // The grid spans the whole selected range: one day, a week, a full month,
  // a year, or a custom span. Wider ranges render as narrower columns.
  const reload = useCallback(async () => {
    try {
      setError(null);
      setWeek(await trackerApi.getWeek(range.fromIso, range.toIso));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [range.fromIso, range.toIso]);

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

  const saveDuration = async (
    minutes: number,
    note: string,
    isPackageStart: boolean
  ) => {
    if (!editing) return;
    await trackerApi.upsertActivity({
      date: editing.dateIso,
      category_id: editing.category.id,
      duration_minutes: minutes,
      note: note || null,
      is_package_start: isPackageStart,
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
          onLayout={setGridGutter}
          onCellClick={(category, dateIso) => setEditing({ category, dateIso })}
          onViewPhysical={async (dateIso) => {
            try {
              setViewSession(await trainingApi.getSessionByDate(dateIso));
            } catch (e) {
              setError(e instanceof Error ? e.message : String(e));
            }
          }}
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
        gutterPx={gridGutter}
      />

      {editing && (
        <Modal
          title={`${editing.category.label} · ${editing.dateIso}`}
          onClose={() => setEditing(null)}
        >
          {editing.category.type === "duration" && (
            <DurationEditor
              category={editing.category}
              dateIso={editing.dateIso}
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

      {viewSession && (
        <Modal
          title={`💪 Training Center · ${viewSession.done_on ?? ""}`}
          onClose={() => setViewSession(null)}
        >
          <SessionCard
            session={viewSession}
            readOnly
            onTick={() => {}}
            onComplete={() => {}}
          />
        </Modal>
      )}
    </div>
  );
}
