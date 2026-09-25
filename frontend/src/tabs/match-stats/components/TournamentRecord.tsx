import { useState } from "react";
import { useLoad, useMutate } from "../../../shared/useApi";
import { dmyDate, prettyDate } from "../../../shared/dates";
import EloDeltaChip from "../../../shared/ui/EloDeltaChip";
import { ROUND_LABEL, matchupOf } from "../../../shared/matches";
import type { TournamentRound } from "../../../shared/matches";
import {
  PLACEMENT_LABEL,
  entryLabel,
  isLeague,
  tournamentIcon,
} from "../../../shared/tournaments";
// The knocked-out toggle is the Daily Tracker's endpoint — reused, not
// duplicated, so both surfaces stay one PATCH.
import { tournamentApi } from "../../daily-tracker/api";
import { matchStatsApi } from "../api";
import type { RecordEntry, TournamentRecordResponse } from "../types";

// "How far did I get" in one phrase: a derived medal placement (with the
// flat ELO bonus it earned) when the matches decide one, otherwise the
// deepest decided round.
function resultLabel(rec: RecordEntry, league: boolean): string {
  // League: W–L (rendered next to this label) is the whole result.
  if (league) return rec.matches.length ? "League" : "No matches entered";
  const p = rec.entry.final_placement;
  if (p) {
    const bonus = rec.entry.bonus_points ? ` +${rec.entry.bonus_points}` : "";
    return `${PLACEMENT_LABEL[p] ?? p}${bonus}`;
  }
  const r = rec.round_reached;
  if (!r) return "No matches entered";
  if (r === "group") return "Group stage";
  const name = ROUND_LABEL[r as TournamentRound] ?? r;
  // Won the deepest entered round → later rounds are missing (the entry's
  // data_warning chip says so); "Reached" is the honest label meanwhile.
  return rec.reached_won ? `Reached ${name}` : `Stopped at ${name}`;
}

function MatchTable({ rec, league }: { rec: RecordEntry; league: boolean }) {
  if (rec.matches.length === 0) {
    return <p className="stats-empty">No matches entered for this event.</p>;
  }
  return (
    <table className="trec-table">
      <thead>
        <tr>
          <th>Date</th>
          {!league && <th>Round</th>}
          <th>Match</th>
          <th>Score</th>
          <th>ELO</th>
        </tr>
      </thead>
      <tbody>
        {rec.matches.map((m) => (
          <tr key={m.id}>
            <td className="trec-td-date">{dmyDate(m.date)}</td>
            {!league && (
              <td>
                {m.round ? ROUND_LABEL[m.round as TournamentRound] ?? m.round : "—"}
              </td>
            )}
            <td className="trec-td-match">{matchupOf(m)}</td>
            <td className={m.won == null ? "" : m.won ? "trec-w" : "trec-l"}>
              {m.my_sets}–{m.opp_sets}
              {m.won == null ? "" : m.won ? " W" : " L"}
            </td>
            <td className="trec-td-elo">
              {m.elo_delta == null ? (
                "—"
              ) : (
                <EloDeltaChip delta={m.elo_delta} />
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function TournamentRecord() {
  const { data, error, loading, reload } = useLoad<TournamentRecordResponse>(
    () => matchStatsApi.tournamentRecord(),
    []
  );
  const { run, error: mutError, busy, clearError } = useMutate();
  const [openId, setOpenId] = useState<number | null>(null);
  const tours = data?.tournaments ?? [];

  // Un-mark a mis-clicked knocked-out: once EVERY entry of a tournament is
  // ☠ the card retires here, where nothing was clickable — a one-way trap
  // (hit twice on 2026-08-23). Un-marking may move the tournament back to
  // the Daily Tracker's upcoming cards (it leaves this list on reload).
  const unmark = async (entryId: number) => {
    const ok = await run(() => tournamentApi.setEliminated(entryId, false));
    if (ok !== undefined) reload();
  };

  return (
    <section className="stats-card trec">
      <h3>🏅 Tournament Record</h3>
      <p className="trec-sub">
        Tournaments you've played and how far you went — derived from the
        matches logged in the Daily Tracker. Click one for every match.
      </p>
      {error && <div className="pb-error">{error}</div>}
      {mutError && (
        <div className="pb-error" onClick={clearError}>
          {mutError}
        </div>
      )}
      {loading && !data && <div className="loading">Loading…</div>}
      {!loading && data && tours.length === 0 && (
        <p className="stats-empty">
          No past tournaments yet. Register tournaments in the Daily Tracker
          and link their matches — the record builds itself.
        </p>
      )}

      {tours.map((t) => {
        const open = openId === t.id;
        return (
          <div key={t.id} className={`trec-card${open ? " open" : ""}`}>
            <div
              className="trec-head"
              onClick={() => setOpenId(open ? null : t.id)}
            >
              <div className="trec-title">
                <b>
                  {tournamentIcon(t)} {t.name}
                </b>
                <span className="trec-date">
                  {prettyDate(t.start_date)}
                  {t.end_date ? ` – ${prettyDate(t.end_date)}` : ""}
                  {t.location ? ` · ${t.location}` : ""}
                </span>
              </div>
              <div className="trec-entries">
                {t.entries.map((rec) => (
                  <span key={rec.entry.id} className="trec-entry">
                    <span className="trec-entry-label">
                      {entryLabel(rec.entry)}
                    </span>
                    <b className="trec-result">{resultLabel(rec, isLeague(t))}</b>
                    {(rec.wins > 0 || rec.losses > 0) && (
                      <span className="trec-wl">
                        {rec.wins}W–{rec.losses}L
                      </span>
                    )}
                    {rec.entry.data_warning && (
                      <span className="trec-warn" title={rec.entry.data_warning}>
                        ⚠
                      </span>
                    )}
                    {rec.entry.eliminated && (
                      <button
                        className="trec-out"
                        disabled={busy}
                        title="Knocked out — click to un-mark (the tournament goes back to the Daily Tracker if its days aren't over)"
                        onClick={(e) => {
                          e.stopPropagation(); // the head click toggles expand
                          void unmark(rec.entry.id);
                        }}
                      >
                        ☠ out · un-mark
                      </button>
                    )}
                  </span>
                ))}
              </div>
              <span className="trec-caret">{open ? "▾" : "▸"}</span>
            </div>
            {open && (
              <div className="trec-detail">
                {t.entries.map((rec) => (
                  <div key={rec.entry.id} className="trec-entry-detail">
                    {t.entries.length > 1 && <h4>{entryLabel(rec.entry)}</h4>}
                    <MatchTable rec={rec} league={isLeague(t)} />
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </section>
  );
}
