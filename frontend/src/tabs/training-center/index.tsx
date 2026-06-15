import { useCallback, useEffect, useState } from "react";
import { trainingApi } from "./api";
import DayGrid from "./components/DayGrid";
import FeedbackModal from "./components/FeedbackModal";
import Heatmap from "./components/Heatmap";
import LevelSwitcher from "./components/LevelSwitcher";
import SessionCard from "./components/SessionCard";
import WeeklySummary from "./components/WeeklySummary";
import WorkoutPlayer from "./components/WorkoutPlayer";
import type {
  DayTile,
  Levels,
  Pain,
  Program,
  Report,
  Rpe,
  TrainingSession,
} from "./types";

export default function TrainingCenter() {
  const [today, setToday] = useState<TrainingSession | null>(null);
  const [program, setProgram] = useState<Program | null>(null);
  const [levels, setLevels] = useState<Levels | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [viewLevel, setViewLevel] = useState<string | null>(null);
  const [detail, setDetail] = useState<TrainingSession | null>(null);
  const [readOnly, setReadOnly] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [askFeedback, setAskFeedback] = useState(false);
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
      setDetail(t);
      setReadOnly(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const fail = (e: unknown) =>
    setError(e instanceof Error ? e.message : String(e));

  const isCurrentLevelView = !!today && program?.level === today.level;
  // Only the live (editable) open session can be played/edited.
  const editable = !!detail && !readOnly;

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
      const lastDone = [...p.tiles].reverse().find((t) => t.status === "done");
      if (lastDone) {
        const s = await trainingApi.getSession(level, lastDone.day_index);
        setDetail(s);
        setReadOnly(true);
      }
    } catch (e) {
      fail(e);
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
      fail(e);
    }
  };

  // Apply an updated session returned by a mutation to local state.
  const applySession = (updated: TrainingSession) => {
    setDetail(updated);
    if (today && updated.id === today.id) setToday(updated);
  };

  const tick = async (itemId: number, done: boolean) => {
    if (!detail || readOnly) return;
    try {
      applySession(
        await trainingApi.tickItem(detail.level, detail.day_index, itemId, done)
      );
    } catch (e) {
      fail(e);
    }
  };

  const substitute = async (itemId: number, key: string) => {
    if (!detail || readOnly) return;
    try {
      applySession(
        await trainingApi.substitute(detail.level, detail.day_index, itemId, key)
      );
    } catch (e) {
      fail(e);
    }
  };

  const skip = async (itemId: number, skipped: boolean) => {
    if (!detail || readOnly) return;
    try {
      applySession(
        await trainingApi.skip(detail.level, detail.day_index, itemId, skipped)
      );
    } catch (e) {
      fail(e);
    }
  };

  const submitFeedback = async (pain: Pain, rpe: Rpe, doneOn: string) => {
    if (!detail) return;
    try {
      setAskFeedback(false);
      await trainingApi.complete(detail.level, detail.day_index, {
        pain,
        rpe,
        done_on: doneOn,
      });
      await load();
    } catch (e) {
      fail(e);
    }
  };

  if (error && !program) return <div className="tc-error">Lỗi: {error}</div>;
  if (!program || !today || !detail || !levels || !report)
    return <div className="tc-loading">Đang tải…</div>;

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
      <Heatmap doneDates={report.done_dates} streak={report.current_streak} />

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
        onComplete={() => setAskFeedback(true)}
        onSubstitute={substitute}
        onSkip={skip}
        onStart={editable ? () => setPlaying(true) : undefined}
      />

      {playing && editable && (
        <WorkoutPlayer
          session={detail}
          onTickItem={tick}
          onFinish={() => {
            setPlaying(false);
            setAskFeedback(true);
          }}
          onClose={() => {
            setPlaying(false);
            void load();
          }}
        />
      )}

      {askFeedback && (
        <FeedbackModal
          onSubmit={submitFeedback}
          onClose={() => setAskFeedback(false)}
        />
      )}
    </div>
  );
}
