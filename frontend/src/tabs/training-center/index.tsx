import { useCallback, useEffect, useState } from "react";
import { trainingApi } from "./api";
import DayGrid from "./components/DayGrid";
import LevelSwitcher from "./components/LevelSwitcher";
import SessionCard from "./components/SessionCard";
import WeeklySummary from "./components/WeeklySummary";
import type {
  DayTile,
  Levels,
  Program,
  Report,
  TrainingSession,
} from "./types";

export default function TrainingCenter() {
  const [today, setToday] = useState<TrainingSession | null>(null);
  const [program, setProgram] = useState<Program | null>(null);
  const [levels, setLevels] = useState<Levels | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  // Which level's grid is shown (defaults to the current level).
  const [viewLevel, setViewLevel] = useState<string | null>(null);
  // The session shown in the detail panel + whether it is editable.
  const [detail, setDetail] = useState<TrainingSession | null>(null);
  const [readOnly, setReadOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [t, lv, rep] = await Promise.all([
        trainingApi.getToday(),
        trainingApi.getLevels(),
        trainingApi.getReport(),
      ]);
      const p = await trainingApi.getProgram(t.level);
      setToday(t);
      setLevels(lv);
      setReport(rep);
      setProgram(p);
      setViewLevel(t.level);
      // Keep the detail panel on the open session after a reload.
      setDetail(t);
      setReadOnly(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const isCurrentLevelView = !!today && program?.level === today.level;

  const switchLevel = async (level: string) => {
    if (!today) return;
    try {
      const p = await trainingApi.getProgram(level);
      setProgram(p);
      setViewLevel(level);
      if (level === today.level) {
        setDetail(today);
        setReadOnly(false);
        return;
      }
      // Browsing another (completed) level: show its last done session read-only.
      const lastDone = [...p.tiles].reverse().find((t) => t.status === "done");
      if (lastDone) {
        const s = await trainingApi.getSession(level, lastDone.day_index);
        setDetail(s);
        setReadOnly(true);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const pickTile = async (tile: DayTile) => {
    if (!program || !today) return;
    if (
      isCurrentLevelView &&
      (tile.status === "unlocked" || tile.day_index === today.day_index)
    ) {
      setDetail(today);
      setReadOnly(false);
      return;
    }
    try {
      const s = await trainingApi.getSession(program.level, tile.day_index);
      setDetail(s);
      setReadOnly(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const tick = async (itemId: number, done: boolean) => {
    if (!detail || readOnly) return;
    try {
      const updated = await trainingApi.tickItem(
        detail.level,
        detail.day_index,
        itemId,
        done
      );
      setDetail(updated);
      if (today && updated.day_index === today.day_index) setToday(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const complete = async () => {
    if (!detail || readOnly) return;
    try {
      await trainingApi.complete(detail.level, detail.day_index);
      await load(); // advances the open session + refreshes grid/levels/report
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (error && !program) {
    return <div className="tc-error">Lỗi: {error}</div>;
  }
  if (!program || !today || !detail || !levels || !report) {
    return <div className="tc-loading">Đang tải…</div>;
  }

  return (
    <div className="training-center">
      <header className="tc-header">
        <div className="tc-header-top">
          <span className="tc-plan">💪 Training Center</span>
          <span className="tc-level">
            {program.level_vi}
            {program.cycle > 1 ? ` · Vòng ${program.cycle}` : ""}
          </span>
        </div>
        <div className="tc-goal">{program.goal_vi}</div>
        <div className="tc-safety">🦵 {program.safety_note}</div>
        <div className="tc-progress-row">
          <div className="tc-progress-bar">
            <div
              className="tc-progress-fill"
              style={{ width: `${program.progress_pct}%` }}
            />
          </div>
          <span className="tc-progress-label">
            {program.completed} / {program.total_sessions} buổi
          </span>
        </div>
      </header>

      <WeeklySummary report={report} />

      <LevelSwitcher
        levels={levels.levels}
        selected={viewLevel ?? program.level}
        currentLevel={levels.current_level}
        onSelect={switchLevel}
      />

      {error && <div className="tc-error">{error}</div>}

      <DayGrid
        tiles={program.tiles}
        activeDay={isCurrentLevelView ? detail.day_index : null}
        onPick={pickTile}
      />

      <SessionCard
        session={detail}
        readOnly={readOnly}
        onTick={tick}
        onComplete={complete}
      />
    </div>
  );
}
