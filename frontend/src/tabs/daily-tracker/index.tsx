import { useEffect, useMemo, useRef, useState } from "react";
import type { Category, MatchIn, TournamentsResponse, WeekResponse } from "./types";
import { tournamentApi, trackerApi } from "./api";
import { fromIso, startOfMonth, toIso } from "../../shared/dates";
import type { Mode } from "../../shared/period";
import { resolveRange, stepAnchor } from "../../shared/period";
import { useLoad, useMutate } from "../../shared/useApi";
import PeriodControl from "../../shared/ui/PeriodControl";
import WeekGrid from "./components/WeekGrid";
import Modal from "../../shared/ui/Modal";
import DurationEditor from "./components/editors/DurationEditor";
import MatchEditor from "./components/editors/MatchEditor";
import ChecklistEditor from "./components/editors/ChecklistEditor";
import NoteEditor from "./components/editors/NoteEditor";
import AnalysisPanel from "./components/AnalysisPanel";
import TournamentStrip from "./components/tournaments/TournamentStrip";
import TournamentSection from "./components/tournaments/TournamentSection";
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
  const {
    data: week,
    error: loadError,
    reload,
  } = useLoad<WeekResponse>(
    () => trackerApi.getWeek(range.fromIso, range.toIso),
    [range.fromIso, range.toIso]
  );
  const { run, error: mutateError, clearError } = useMutate();
  const error = mutateError ?? loadError;

  // Tournaments: one load shared by the strip (top) and the section (bottom);
  // section mutations push the fresh list back via setTournaments.
  const { data: tournData, setData: setTournaments } =
    useLoad<TournamentsResponse>(() => tournamentApi.list(), []);
  const tournaments = tournData?.tournaments ?? [];
  const tournRef = useRef<HTMLDivElement>(null);

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

  // ---- mutations (all reload the week afterwards; a failed call surfaces in
  // the error banner instead of rejecting silently) ----
  const afterMutate = () => {
    reload();
    setDataVersion((v) => v + 1);
  };

  const saveDuration = async (
    minutes: number,
    note: string,
    isPackageStart: boolean
  ) => {
    if (!editing) return;
    const ok = await run(() =>
      trackerApi.upsertActivity({
        date: editing.dateIso,
        category_id: editing.category.id,
        duration_minutes: minutes,
        note: note || null,
        is_package_start: isPackageStart,
      })
    );
    if (ok === undefined) return; // failed → keep the editor open
    setEditing(null);
    afterMutate();
  };

  const clearDuration = async () => {
    if (!editing) return;
    const ok = await run(() =>
      trackerApi.upsertActivity({
        date: editing.dateIso,
        category_id: editing.category.id,
        duration_minutes: 0,
        note: null,
      })
    );
    if (ok === undefined) return;
    setEditing(null);
    afterMutate();
  };

  const addMatch = async (payload: Omit<MatchIn, "date" | "category_id">) => {
    if (!editing) return;
    const ok = await run(() =>
      trackerApi.createMatch({
        date: editing.dateIso,
        category_id: editing.category.id,
        ...payload,
      })
    );
    if (ok === undefined) return;
    afterMutate();
  };

  const deleteMatch = async (id: number) => {
    // DELETE returns 204 (no body) → the api client resolves to undefined,
    // which is also run()'s failure sentinel — wrap so success stays truthy.
    const ok = await run(async () => {
      await trackerApi.deleteMatch(id);
      return true;
    });
    if (ok === undefined) return;
    afterMutate();
  };

  const savePhysicalChecks = async (items: string[]) => {
    if (!editing) return;
    const ok = await run(() =>
      trackerApi.setPhysicalChecks(editing.dateIso, items)
    );
    if (ok === undefined) return;
    setEditing(null);
    afterMutate();
  };

  const saveNote = async (text: string) => {
    if (!editing) return;
    const ok = await run(() => trackerApi.setDayNote(editing.dateIso, text));
    if (ok === undefined) return;
    setEditing(null);
    afterMutate();
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

      <TournamentStrip
        tournaments={tournaments}
        onManage={() =>
          tournRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })
        }
      />

      {error && (
        <div className="error-banner" onClick={clearError}>
          ⚠ {error}
        </div>
      )}

      {week ? (
        <WeekGrid
          week={week}
          tournaments={tournaments}
          onLayout={setGridGutter}
          onCellClick={(category, dateIso) => setEditing({ category, dateIso })}
          onViewPhysical={async (dateIso) => {
            const s = await run(() => trainingApi.getSessionByDate(dateIso));
            if (s !== undefined) setViewSession(s);
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

      {/* Bottom by design: input is rare (the strip on top does the daily
          job); ordered below the daily-use Analysis panel. */}
      <div ref={tournRef}>
        <TournamentSection tournaments={tournaments} onData={setTournaments} />
      </div>

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
              // Tournament context: the registered entries of tournaments
              // running on this cell's date (tournament row only) — the
              // editor shows the banner / entry pick / round picker from it.
              tournamentCtx={
                editing.category.key === "tournament_match"
                  ? tournaments
                      .filter(
                        (t) =>
                          t.start_date <= editing.dateIso &&
                          editing.dateIso <= (t.end_date ?? t.start_date)
                      )
                      .flatMap((t) =>
                        t.entries.map((entry) => ({ tournament: t, entry }))
                      )
                  : []
              }
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
              current={week ? week.day_notes[editing.dateIso] ?? "" : ""}
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
