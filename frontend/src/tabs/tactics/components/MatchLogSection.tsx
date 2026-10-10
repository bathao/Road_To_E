// Match log section of the Tactics tab (2026-10-10): the singles matches vs
// this opponent with their charting status, the point charter for the one
// being logged, and the derived report (this match / every charted match).
import { useEffect, useMemo, useState } from "react";
import { useLoad, useMutate } from "../../../shared/useApi";
import { prettyDate } from "../../../shared/dates";
import { resultOf } from "../../../shared/types";
import type { Match } from "../../daily-tracker/types";
import { matchlogApi } from "../api";
import type { MatchLog, MatchLogStatus, PointIn, Serve, ServeIn, SetScore, Stats } from "../types";
import MatchReport from "./MatchReport";
import PointCharter from "./PointCharter";

export default function MatchLogSection({
  opponentId,
  opponentName,
  matches,
}: {
  opponentId: number;
  opponentName: string;
  // Singles matches vs this opponent, newest first (the tab's vsAll).
  matches: Match[];
}) {
  const { run, error, busy, clearError } = useMutate();
  const names = { me: "Thảo", opp: opponentName.split(" ").slice(-1)[0] || opponentName };

  const { data: serves, reload: reloadServes } = useLoad<Serve[]>(() => matchlogApi.getServes(), []);
  const { data: status, reload: reloadStatus } = useLoad<MatchLogStatus[]>(
    () => matchlogApi.status(opponentId),
    [opponentId]
  );
  const { data: oppStats, reload: reloadOppStats } = useLoad<Stats>(
    () => matchlogApi.playerStats(opponentId),
    [opponentId]
  );

  const [selId, setSelId] = useState<number | null>(null);
  useEffect(() => setSelId(null), [opponentId]);
  const selected = matches.find((m) => m.id === selId) ?? null;

  const { data: log, reload: reloadLog } = useLoad<MatchLog | null>(
    () => (selId ? matchlogApi.get(selId) : Promise.resolve(null)),
    [selId]
  );
  const { data: matchStats, reload: reloadMatchStats } = useLoad<Stats | null>(
    () => (selId ? matchlogApi.matchStats(selId) : Promise.resolve(null)),
    [selId]
  );
  const [scope, setScope] = useState<"match" | "all">("match");

  const statusOf = useMemo(() => {
    const m = new Map<number, MatchLogStatus>();
    (status ?? []).forEach((s) => m.set(s.match_id, s));
    return (id: number) => m.get(id);
  }, [status]);

  const afterChange = () => {
    reloadLog();
    reloadMatchStats();
    reloadStatus();
    reloadOppStats();
  };
  const addPoint = async (p: PointIn) => {
    if (!selId) return false;
    const out = await run(() => matchlogApi.addPoint(selId, p));
    if (out === undefined) return false;
    afterChange();
    return true;
  };
  const deletePoint = async (id: number) => {
    const out = await run(() => matchlogApi.deletePoint(id));
    if (out !== undefined) afterChange();
  };
  const saveSets = async (sets: SetScore[]) => {
    if (!selId) return;
    const out = await run(() => matchlogApi.putSets(selId, sets));
    if (out !== undefined) {
      reloadLog();
      reloadStatus();
    }
  };
  const addServe = async (s: ServeIn) => {
    const out = await run(() => matchlogApi.addServe(s));
    if (out !== undefined) reloadServes();
    return out;
  };

  const stats = scope === "match" ? matchStats : oppStats;

  return (
    <section className="tac-matchlog">
      <div className="tac-sec-head">
        <h2>🎬 Match log</h2>
        <span className="tac-hint">
          Click a match (or its Log points › button) to chart it point by point — only the few you want analysed in depth. The numbers below are derived from the points, nothing is typed as prose.
        </span>
      </div>
      {error && (
        <div className="error-banner" onClick={clearError}>⚠ {error}</div>
      )}

      {matches.length === 0 ? (
        <p className="tac-hint">No singles matches vs {opponentName} yet.</p>
      ) : (
        <ul className="ml-matches">
          {matches.map((m) => {
            const st = statusOf(m.id);
            const r = resultOf(m);
            const won = m.my_sets > m.opp_sets;
            return (
              <li
                key={m.id}
                className={`ml-match${m.id === selId ? " active" : ""}`}
                title={m.id === selId ? "Close" : "Open the point charter for this match"}
                onClick={() => { setSelId(m.id === selId ? null : m.id); setScope("match"); }}
              >
                <span className="ml-match-date">{prettyDate(m.date)}</span>
                <span className={`ml-match-res ${won ? "w" : "l"}`}>{r}</span>
                <span className="ml-match-ev">{m.event_name ?? ""}</span>
                <span className={`ml-status${st?.points ? " pts" : st?.sets_typed ? " sets" : ""}`}>
                  {st?.points
                    ? `${st.points} pts charted${st.sets_typed ? ` · ${st.sets_typed} sets` : ""}`
                    : st?.sets_typed
                      ? `${st.sets_typed} set score${st.sets_typed === 1 ? "" : "s"} typed`
                      : "not logged"}
                </span>
                <button
                  type="button"
                  className={`btn${m.id === selId || st?.points ? "" : " primary"}`}
                  onClick={(e) => { e.stopPropagation(); setSelId(m.id === selId ? null : m.id); setScope("match"); }}
                >
                  {m.id === selId ? "Close" : st?.points ? "Open" : "Log points ›"}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {selected && log && serves && (
        <PointCharter
          key={selected.id}
          match={selected}
          names={names}
          serves={serves}
          log={log}
          busy={busy}
          onAddPoint={addPoint}
          onDeletePoint={deletePoint}
          onSaveSets={saveSets}
          onAddServe={addServe}
        />
      )}

      <div className="ml-report-head">
        <h3>📈 Report</h3>
        <div className="ml-seg">
          <button
            type="button"
            className={scope === "match" ? "on acc" : ""}
            disabled={!selected}
            onClick={() => setScope("match")}
          >
            This match
          </button>
          <button
            type="button"
            className={scope === "all" ? "on acc" : ""}
            onClick={() => setScope("all")}
          >
            All charted vs {names.opp}
          </button>
        </div>
      </div>
      {scope === "match" && !selected ? (
        <p className="ml-empty">Open a match above to see its report, or switch to all charted matches.</p>
      ) : stats ? (
        <MatchReport stats={stats} serves={serves ?? []} names={names} />
      ) : (
        <p className="ml-empty">Loading…</p>
      )}
    </section>
  );
}
