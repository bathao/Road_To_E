// Singles Tactics tab (Chiến Thuật): pick an opponent you've played →
// head-to-head history (tiles + charts + match list) → scouting facts
// (about ME = global, never re-asked; about the opponent) → coach interview
// for the gaps → a generated Vietnamese game plan to beat exactly that
// person. SINGLES ONLY throughout — doubles/1v2/2v1 don't inform personal
// tactics (user 2026-08-15); the backend filters the same way.
import { useEffect, useMemo, useRef, useState } from "react";
import { useLoad, useMutate } from "../../shared/useApi";
import { hdcLabel } from "../../shared/matches";
import { startOfMonth, toIso } from "../../shared/dates";
import MatchRowList from "../daily-tracker/components/MatchRowList";
import type { Match } from "../daily-tracker/types";
import RangePicker, {
  resolvePreset,
  type RangePreset,
} from "../match-stats/components/RangePicker";
import { tacticsApi } from "./api";
import { ME_INTAKE, OPP_INTAKE, type IntakeItem } from "./intake";
import FactsPanel from "./components/FactsPanel";
import HandicapBars from "./components/HandicapBars";
import IntakeCard from "./components/IntakeCard";
import ReflectionsSection from "./components/ReflectionsSection";
import MarginTimeline from "./components/MarginTimeline";
import PlanSection from "./components/PlanSection";
import type {
  AnswerIn,
  FactKind,
  FactsOut,
  FactSubject,
  InterviewQuestion,
  Reflection,
  TacticPlan,
} from "./types";

export default function Tactics() {
  const { run, error, busy, clearError } = useMutate();
  const [selId, setSelId] = useState<number | null>(null);

  const { data: opponents } = useLoad(() => tacticsApi.getOpponents(), []);
  const selected = (opponents ?? []).find((o) => o.id === selId) ?? null;

  // Per-opponent loads (facts include the global me-column).
  const { data: allMatches } = useLoad<Match[] | null>(
    () => (selId ? tacticsApi.playerMatches(selId) : Promise.resolve(null)),
    [selId]
  );
  const { data: facts, setData: setFacts } = useLoad<FactsOut | null>(
    () => (selId ? tacticsApi.getFacts(selId) : Promise.resolve(null)),
    [selId]
  );
  const { data: reflections, setData: setReflections } = useLoad<
    Reflection[] | null
  >(() => (selId ? tacticsApi.getReflections(selId) : Promise.resolve(null)), [selId]);
  const { data: plan, setData: setPlan, reload: reloadPlan } = useLoad<
    TacticPlan | null
  >(() => (selId ? tacticsApi.getPlan(selId) : Promise.resolve(null)), [selId]);

  // While a plan is generating, poll every 3s (same contract as the coach).
  useEffect(() => {
    if (plan?.status !== "generating") return;
    const timer = setInterval(() => reloadPlan(), 3000);
    return () => clearInterval(timer);
  }, [plan?.status, reloadPlan]);

  // When a plan lands, re-pull the facts: the coach's background extraction
  // (🧠 me-facts from analysis notes) has usually finished by then too.
  const prevPlanStatus = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (prevPlanStatus.current === "generating" && plan?.status === "done") {
      void refreshFacts();
    }
    prevPlanStatus.current = plan?.status;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- status edge only
  }, [plan?.status]);

  // H2H = SINGLES matches against this person (the endpoint returns every
  // match in any slot/discipline). API order is newest first.
  const vsAll = useMemo(
    () =>
      (allMatches ?? []).filter(
        (m) =>
          !m.is_nonplaying &&
          m.discipline === "singles" &&
          m.opponent_id === selId
      ),
    [allMatches, selId]
  );

  // Time-range filter, same picker as the Profile tab (user 2026-08-15).
  // Default = Last 28 days (user 2026-08-17, supersedes the Lifetime
  // default: recent form matters most for tactics; sparse rivalries just
  // show fewer matches). The preset sticks across opponent switches so
  // ranges compare like-for-like.
  const [preset, setPreset] = useState<RangePreset>("last28");
  const [customFrom, setCustomFrom] = useState<string>(() =>
    toIso(startOfMonth(new Date()))
  );
  const [customTo, setCustomTo] = useState<string>(() => toIso(new Date()));
  const firstVsDate = vsAll.length ? vsAll[vsAll.length - 1].date : null;
  const range = useMemo(
    () => resolvePreset(preset, customFrom, customTo, firstVsDate),
    [preset, customFrom, customTo, firstVsDate]
  );
  const vs = useMemo(
    () => vsAll.filter((m) => m.date >= range.fromIso && m.date <= range.toIso),
    [vsAll, range.fromIso, range.toIso]
  );
  const decidedAsc = useMemo(
    () => [...vs].reverse().filter((m) => m.my_sets !== m.opp_sets),
    [vs]
  );
  const wins = decidedAsc.filter((m) => m.my_sets > m.opp_sets).length;
  const losses = decidedAsc.length - wins;
  // Current streak, newest backwards ("L3" = lost the last 3).
  const lastDecided = decidedAsc[decidedAsc.length - 1];
  const lastWon = lastDecided ? lastDecided.my_sets > lastDecided.opp_sets : false;
  let streak = 0;
  for (let i = decidedAsc.length - 1; i >= 0; i--) {
    if ((decidedAsc[i].my_sets > decidedAsc[i].opp_sets) !== lastWon) break;
    streak += 1;
  }
  const lastKelo = lastDecided
    ? hdcLabel(lastDecided.handicap, lastDecided.handicap_pattern) ?? "even"
    : "—";

  // ---- scouting mutations (facts refresh via one GET — keeps both columns
  // consistent no matter which side changed) ----
  const refreshFacts = async () => {
    if (!selId) return;
    const out = await run(() => tacticsApi.getFacts(selId));
    if (out !== undefined) setFacts(out);
  };
  const addFact = (playerId: number | null) => async (kind: FactKind, text: string) => {
    const out = await run(() => tacticsApi.addFact(playerId, kind, text));
    if (out === undefined) return false;
    await refreshFacts();
    return true;
  };
  // Intake answers are keyed facts — the backend upserts on (player_id, key),
  // so the question disappears from the card once its fact exists.
  const answerIntake = (playerId: number | null) => async (item: IntakeItem, text: string) => {
    const out = await run(() => tacticsApi.addFact(playerId, item.kind, text, item.key));
    if (out === undefined) return false;
    await refreshFacts();
    return true;
  };
  const editFact = async (id: number, text: string) => {
    const out = await run(() => tacticsApi.updateFact(id, text));
    if (out === undefined) return false;
    await refreshFacts();
    return true;
  };
  const deleteFact = async (id: number) => {
    const out = await run(() => tacticsApi.deleteFact(id));
    if (out !== undefined) await refreshFacts();
  };

  // ---- reflections (refresh via one GET, same pattern as facts) ----
  const refreshReflections = async () => {
    if (!selId) return;
    const out = await run(() => tacticsApi.getReflections(selId));
    if (out !== undefined) setReflections(out);
  };
  const addReflection = async (text: string) => {
    if (!selId) return false;
    const out = await run(() => tacticsApi.addReflection(selId, text));
    if (out === undefined) return false;
    await refreshReflections();
    return true;
  };
  const editReflection = async (id: number, text: string) => {
    const out = await run(() => tacticsApi.updateReflection(id, text));
    if (out === undefined) return false;
    await refreshReflections();
    return true;
  };
  const deleteReflection = async (id: number) => {
    const out = await run(() => tacticsApi.deleteReflection(id));
    if (out !== undefined) await refreshReflections();
  };

  // ---- interview ----
  const [questions, setQuestions] = useState<InterviewQuestion[] | null>(null);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  // Per-question save-target override: the model has mis-tagged subjects
  // (an about-ME question tagged 'opponent' filed the answer into the wrong
  // scouting column, user 2026-08-17) — the toggle makes the target visible
  // and correctable before saving.
  const [subjects, setSubjects] = useState<Record<number, FactSubject>>({});
  const [asking, setAsking] = useState(false);
  const ask = async () => {
    if (!selId) return;
    setAsking(true);
    try {
      const out = await run(() => tacticsApi.interview(selId));
      if (out !== undefined) {
        setQuestions(out.questions);
        setAnswers({});
        setSubjects({});
      }
    } finally {
      setAsking(false);
    }
  };
  const saveAnswers = async () => {
    if (!selId || !questions) return;
    const items: AnswerIn[] = questions
      .map((q, i) => ({
        ...q,
        subject: subjects[i] ?? q.subject,
        answer: (answers[i] ?? "").trim(),
      }))
      .filter((q) => q.answer);
    if (items.length === 0) {
      setQuestions(null);
      return;
    }
    const out = await run(() => tacticsApi.saveAnswers(selId, items));
    if (out !== undefined) {
      setFacts(out);
      setQuestions(null);
    }
  };

  // ---- plan ----
  const generatePlan = async () => {
    if (!selId) return;
    const out = await run(() => tacticsApi.generatePlan(selId));
    if (out !== undefined) setPlan(out);
  };

  const pickOpponent = (id: number | null) => {
    setSelId(id);
    setQuestions(null);
    setAnswers({});
    clearError();
  };

  return (
    <div className="tab-tactics">
      <div className="tac-head">
        <h1>🎯 Singles Tactics</h1>
        <select
          className="pb-select tac-pick"
          value={selId ?? ""}
          onChange={(e) => pickOpponent(e.target.value ? Number(e.target.value) : null)}
        >
          <option value="">Select an opponent…</option>
          {(opponents ?? []).map((o) => (
            <option key={o.id} value={o.id}>
              {o.name} · {o.matches_vs} matches ({o.wins}W–{o.losses}L)
              {o.plays_pips ? " · pips" : ""}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <div className="error-banner" onClick={clearError}>
          ⚠ {error}
        </div>
      )}

      {!selected && (
        <p className="tac-hint">
          Pick someone you have played in singles — their head-to-head
          history, your scouting notes and the coach's game plan for beating
          them all live here. (Doubles / 1v2 / 2v1 don't count in this tab.)
        </p>
      )}

      {selected && (
        <>
          <section className="tac-h2h">
            <div className="tac-sec-head">
              <h2>📊 Head-to-head vs {selected.name}</h2>
              <RangePicker
                preset={preset}
                customFrom={customFrom}
                customTo={customTo}
                firstDate={firstVsDate}
                onPreset={setPreset}
                onCustomFrom={setCustomFrom}
                onCustomTo={setCustomTo}
              />
            </div>
            <div className="tac-tiles">
              <div className="stat-card">
                <div className="stat-card-title">Record</div>
                <div className="stat-big">
                  {wins}W<span className="stat-of">–{losses}L</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Win rate</div>
                <div className="stat-big">
                  {decidedAsc.length
                    ? `${Math.round((wins / decidedAsc.length) * 100)}%`
                    : "—"}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Streak</div>
                <div className="stat-big">
                  {lastDecided ? `${lastWon ? "W" : "L"}${streak}` : "—"}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Latest handicap</div>
                <div className="stat-big tac-tile-small">{lastKelo}</div>
              </div>
            </div>
            <MarginTimeline matches={decidedAsc} />
            <HandicapBars matches={decidedAsc} />
            <details className="tac-matches">
              <summary>
                {vs.length === vsAll.length
                  ? `All ${vs.length} singles matches`
                  : `${vs.length} of ${vsAll.length} singles matches in range`}
              </summary>
              <MatchRowList matches={vs} />
            </details>
          </section>

          <section className="tac-scouting">
            <div className="tac-sec-head">
              <h2>🔍 Scouting</h2>
              <button className="btn" disabled={busy || asking} onClick={() => void ask()}>
                {asking ? "⏳ Coach is preparing questions…" : "🎤 Interview me"}
              </button>
            </div>
            {questions && (
              <div className="tac-interview">
                {questions.length === 0 && (
                  <p className="tac-hint">
                    The coach has no questions — the scouting file is thick
                    enough. Generate the plan.
                  </p>
                )}
                {questions.map((q, i) => (
                  <div key={i} className="tac-question">
                    <label>
                      <span className="tac-subj-toggle" title="Where this answer will be filed — click to correct">
                        {(["me", "opponent"] as FactSubject[]).map((s) => (
                          <button
                            key={s}
                            type="button"
                            className={`btn tac-chip${(subjects[i] ?? q.subject) === s ? " tac-chip-on" : ""}`}
                            onClick={() => setSubjects((m) => ({ ...m, [i]: s }))}
                          >
                            {s === "me" ? "About me" : selected.name}
                          </button>
                        ))}
                      </span>
                      {q.question}
                    </label>
                    <input
                      type="text"
                      className="pb-input"
                      placeholder="Answer (leave blank to skip)"
                      value={answers[i] ?? ""}
                      onChange={(e) =>
                        setAnswers((a) => ({ ...a, [i]: e.target.value }))
                      }
                    />
                  </div>
                ))}
                {questions.length > 0 && (
                  <div className="tac-interview-actions">
                    <button className="btn primary" disabled={busy} onClick={() => void saveAnswers()}>
                      💾 Save answers as facts
                    </button>
                    <button className="btn" onClick={() => setQuestions(null)}>
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            )}
            <div className="tac-facts">
              <FactsPanel
                title="About me (all opponents)"
                hint="Saved once, remembered forever — the coach never re-asks these. It also files anything about you it spots in your analysis notes (🧠)."
                facts={facts?.me ?? []}
                busy={busy}
                intake={
                  <IntakeCard
                    items={ME_INTAKE}
                    facts={facts?.me ?? []}
                    busy={busy}
                    onAnswer={answerIntake(null)}
                  />
                }
                onAdd={addFact(null)}
                onEdit={editFact}
                onDelete={deleteFact}
              />
              <FactsPanel
                title={`About ${selected.name}`}
                facts={facts?.opponent ?? []}
                busy={busy}
                intake={
                  <IntakeCard
                    items={OPP_INTAKE}
                    facts={facts?.opponent ?? []}
                    busy={busy}
                    onAnswer={answerIntake(selected.id)}
                  />
                }
                onAdd={addFact(selected.id)}
                onEdit={editFact}
                onDelete={deleteFact}
              />
            </div>
          </section>

          <ReflectionsSection
            opponentName={selected.name}
            reflections={reflections ?? []}
            busy={busy}
            onAdd={addReflection}
            onEdit={editReflection}
            onDelete={deleteReflection}
          />

          <PlanSection
            plan={plan ?? null}
            opponentName={selected.name}
            onGenerate={() => void generatePlan()}
            busy={busy}
          />
        </>
      )}
    </div>
  );
}
