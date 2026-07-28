import { useCallback, useEffect, useState } from "react";
import { headCoachApi } from "./api";
import { useLoad, useMutate } from "../../shared/useApi";
import CoachChat from "./components/CoachChat";
import CoachNotes from "./components/CoachNotes";
import DevLogs from "./components/DevLogs";
import { fmtTime } from "./fmt";
import type { Assessment, Directive, DirectiveProgress, NotesOut } from "./types";

const AREA: Record<string, { icon: string; label: string }> = {
  training: { icon: "💪", label: "Fitness" },
  playing_hours: { icon: "⏱️", label: "Playing hours" },
  matches: { icon: "🏓", label: "Matches" },
  skill: { icon: "🎯", label: "Skill" },
  tactics: { icon: "♟️", label: "Tactics" },
  recovery: { icon: "🛌", label: "Recovery" },
  // Aliases the model sometimes emits instead of the canonical areas —
  // mapped so the card never shows a raw English key.
  playing: { icon: "⏱️", label: "Playing hours" },
  training_hours: { icon: "⏱️", label: "Training hours" },
  physical_training: { icon: "💪", label: "Fitness" },
};

function areaOf(d: Directive) {
  return AREA[d.area] ?? { icon: "📌", label: d.area };
}

// What each trackable metric actually measures (mirrors backend _week_actual)
// — shown next to the progress bar so the order text can't be misread.
const METRIC_SCOPE: Record<string, string> = {
  physical_sessions_per_week: "Training Center fitness sessions",
  racket_hours_per_week: "total racket time: practice + matches",
  coach_hours_per_week: "coach hours only",
  matches_per_week: "all matches, singles and doubles",
  singles_matches_per_week: "singles matches only",
  doubles_matches_per_week: "doubles matches only",
  matches_vs_pips_per_week: "matches vs pips opponents",
};

export default function HeadCoach() {
  const [generating, setGenerating] = useState(false);
  const {
    data,
    error: loadError,
    loading,
    reload,
  } = useLoad<Assessment>(() => headCoachApi.getAssessment(), []);
  const { run, error: mutateError, clearError } = useMutate();
  const error = mutateError ?? loadError;

  // Live weekly progress for trackable directives (re-fetched when a new
  // verdict arrives, since the deps include the assessment id).
  const { data: progress } = useLoad(
    () => headCoachApi.getDirectiveProgress(),
    [data?.id]
  );
  const progressByIndex = new Map<number, DirectiveProgress>(
    (progress?.items ?? []).map((p) => [p.index, p])
  );

  // The coach's notebook — refreshed after each chat reply (the coach may
  // have auto-written notes) and edited from the notes panel.
  const {
    data: notesData,
    reload: reloadNotes,
    setData: setNotesData,
  } = useLoad<NotesOut>(() => headCoachApi.getNotes(), []);
  const { run: runNotes, busy: notesBusy, error: notesError } = useMutate();
  const addNote = useCallback(
    async (text: string) => {
      const out = await runNotes(() => headCoachApi.addNote(text));
      if (out !== undefined) setNotesData(out);
      return out !== undefined; // tells the input whether to clear
    },
    [runNotes, setNotesData]
  );
  const deleteNote = useCallback(
    async (id: number) => {
      const out = await runNotes(() => headCoachApi.deleteNote(id));
      if (out !== undefined) setNotesData(out);
    },
    [runNotes, setNotesData]
  );

  // On mount, resume the "generating" state if a run is already in flight
  // (e.g. the tab was switched away and back while the local model worked).
  useEffect(() => {
    let alive = true;
    headCoachApi
      .getStatus()
      .then((s) => {
        if (alive && s.status === "generating") setGenerating(true);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // While generating, poll the status every 3s; when the run finishes, stop
  // and refetch the completed assessment (or surface the error). A rejected
  // poll (dev-server reload, one dropped request) is transient — keep
  // polling; only a *returned* error status is terminal.
  useEffect(() => {
    if (!generating) return;
    const timer = setInterval(async () => {
      let s;
      try {
        s = await headCoachApi.getStatus();
      } catch {
        return; // transient fetch failure — try again next tick
      }
      if (s.status === "generating") return;
      setGenerating(false);
      if (s.status === "error") {
        const msg = s.error_msg || "Analysis failed.";
        void run(() => Promise.reject(new Error(msg))); // surface via shared error state
        return;
      }
      reload();
    }, 3000);
    return () => clearInterval(timer);
  }, [generating, reload, run]);

  const generate = async () => {
    clearError();
    const started = await run(() => headCoachApi.generate());
    if (started !== undefined) setGenerating(true);
  };

  const m = data?.sources.match ?? {};
  const detail = data?.sources.match_detail ?? {};
  const training = data?.sources.training ?? {};
  const notes = data?.sources.notes ?? [];

  return (
    <div className="hc">
      <div className="hc-main">
      <div className="hc-top">
        <div>
          <h2 className="hc-title">🧠 Head Coach</h2>
          <p className="hc-sub">
            Your personal coach — reviews all of your data and delivers a
            strict assessment + a plan.
          </p>
        </div>
        <button className="btn primary" onClick={generate} disabled={generating}>
          {generating ? "⏳ Analyzing…" : data?.empty ? "First analysis" : "Re-analyze"}
        </button>
      </div>

      {generating && (
        <div className="hc-note">
          The coach is reviewing your data (local model running in the
          background — you can switch tabs and come back, the result will
          appear automatically)…
        </div>
      )}
      {error && <div className="hc-error">⚠️ {error}</div>}

      {!loading && data?.empty && !generating && (
        <div className="hc-empty">
          No assessment yet. Click <b>“First analysis”</b> to have the head
          coach read your technique profile, fitness, match results and
          tactics.
        </div>
      )}

      {data && !data.empty && (
        <>
          <section className="hc-overall">
            <h3>Overall assessment</h3>
            <p>{data.overall_assessment}</p>
          </section>

          {data.directives.length > 0 && (
            <section className="hc-section">
              <h3>📋 Directives</h3>
              <div className="hc-directives">
                {data.directives.map((d, i) => {
                  const a = areaOf(d);
                  const p = progressByIndex.get(i);
                  return (
                    <div key={i} className="hc-directive">
                      <div className="hc-directive-head">
                        <span className="hc-area">{a.icon} {a.label}</span>
                        {d.target && <span className="hc-target">{d.target}</span>}
                      </div>
                      <div className="hc-order">{d.order}</div>
                      {d.reason && <div className="hc-reason">↳ {d.reason}</div>}
                      {p && (
                        <div
                          className="hc-progress"
                          title="This week's progress, computed automatically from logged data (Monday → today)"
                        >
                          <div className="hc-progress-track">
                            <div
                              className={`hc-progress-fill${p.pct >= 100 ? " done" : ""}`}
                              style={{ width: `${p.pct}%` }}
                            />
                          </div>
                          <span className="hc-progress-label">
                            This week: <b>{p.actual}</b>/{p.value} {p.unit_vi}
                            {p.pct >= 100 ? " ✓" : ""}
                            {METRIC_SCOPE[p.metric] && (
                              <span className="hc-progress-scope">
                                {" "}· {METRIC_SCOPE[p.metric]}
                              </span>
                            )}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {data.top_priorities.length > 0 && (
            <section className="hc-section">
              <h3>🎯 Priorities</h3>
              <ol className="hc-priorities">
                {data.top_priorities.map((p, i) => (
                  <li key={i}>
                    <div className="hc-pri-title">{p.title}</div>
                    {p.why && <div className="hc-pri-why">{p.why}</div>}
                    {p.source && <span className="hc-chip">{p.source}</span>}
                  </li>
                ))}
              </ol>
            </section>
          )}

          {data.week_plan.length > 0 && (
            <section className="hc-section">
              <h3>🗓️ Week plan</h3>
              <div className="hc-week">
                {data.week_plan.map((d, i) => (
                  <div key={i} className="hc-day">
                    <div className="hc-day-name">{d.day}</div>
                    <div className="hc-day-focus">{d.focus}</div>
                    <div className="hc-day-detail">{d.detail}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {data.watch_items.length > 0 && (
            <section className="hc-section hc-watch">
              <h3>⚠️ Watch items</h3>
              <ul>
                {data.watch_items.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </section>
          )}

          <details className="hc-sources">
            <summary>📊 Data sources the coach read</summary>
            <div className="hc-source-grid">
              <div>Time range: {data.sources.generated_for_range}</div>
              <div>
                Matches (90 days): singles {m.singles?.played ?? "—"} · doubles{" "}
                {m.doubles?.played ?? "—"} · pips {m.vs_pips?.played ?? "—"} · total{" "}
                {m.overall?.played ?? "—"}
              </div>
              <div>
                Deep dive ({detail.window ?? "—"}): casual{" "}
                {detail.practice?.played ?? "—"} · light stakes{" "}
                {detail.official?.played ?? "—"} · tournament{" "}
                {detail.tournament?.played ?? "—"} · head-to-head{" "}
                {detail.top_h2h?.length ?? 0} opponents
              </div>
              <div>
                Fitness: level {training.level ?? "—"} ·{" "}
                {training.sessions_last_7d ?? 0} sessions/7 days · Notes: last{" "}
                {notes.length} days
              </div>
            </div>
          </details>

          <div className="hc-meta">
            Generated at {fmtTime(data.created_at)} · model {data.model}
          </div>
        </>
      )}
      <DevLogs />
      </div>

      <aside className="hc-side">
        <section className="hc-side-block">
          <h3>💬 Chat with the coach</h3>
          <p className="hc-hint">
            Set short-term goals, report busy schedules, ask about your stats —
            the coach answers from real data and remembers every exchange
            (stored in the database).
          </p>
          <CoachChat onCoachReply={reloadNotes} />
        </section>
        <section className="hc-side-block">
          <h3>📒 Coach's notebook</h3>
          <p className="hc-hint">
            Settled facts — injected into every reply and into the assessment.
          </p>
          <CoachNotes
            notes={notesData?.notes ?? []}
            onAdd={addNote}
            onDelete={deleteNote}
            busy={notesBusy}
            error={notesError}
          />
        </section>
      </aside>
    </div>
  );
}
