import { useMemo, useState } from "react";
import { shortDate } from "../../../shared/dates";
import { DISCIPLINE_LABEL } from "../../../shared/disciplines";
import { fmtDelta } from "../../../shared/format";
import { resultOf } from "../../../shared/types";
import EloCurve from "../../../shared/ui/EloCurve";
import SortableTh, { toggleSort } from "../../../shared/ui/SortableTh";
import type { Sort } from "../../../shared/ui/SortableTh";
import { matchupOf } from "../../../shared/matches";
import type { RatingBreakdown, RatingMover } from "../types";

// The two ELO cards of the Match Stats tab, split so the layout can place
// them independently (curve on its own row, table next to the head-to-head
// lookup). Both are GLOBAL — the rating ignores the tab's
// discipline/category filters (a filtered "rating at end" would lie).

// "ELO over time": the SAME rating curve the Daily Tracker Analysis draws
// (shared/ui/EloCurve — one mental model app-wide).
export function EloCurveCard({
  elo,
  unit,
}: {
  elo: RatingBreakdown;
  unit: "month" | "week" | "day";
}) {
  // The whole range predates the anchor — no rating existed yet.
  if (elo.rating_end === null) return null;
  return (
    <section className="stats-card">
      <div className="elo-head">
        <h3>📈 ELO over time (by {unit})</h3>
        <span
          className="elo-current"
          title="Rating at the end of the visible range"
        >
          {elo.rating_end}
        </span>
        <span
          className={`elo-chip ${elo.total_delta >= 0 ? "elo-up" : "elo-down"}`}
          title="net Δ in the range being viewed"
        >
          {fmtDelta(elo.total_delta)} · {elo.counted} matches
        </span>
      </div>
      <p className="elo-note">
        {elo.rating_start !== null && elo.rating_start !== elo.rating_end
          ? `from ${elo.rating_start} · `
          : ""}
        all ELO-counted matches — not affected by the two filters above
      </p>
      <EloCurve
        elo={elo}
        labelOf={(b) => b.label}
        tipOf={(b) =>
          b.date_from === b.date_to
            ? b.date_from
            : `${b.date_from} → ${b.date_to}`
        }
        fallback={
          <p className="stats-muted">
            Not enough data in this range to draw a line.
          </p>
        }
      />
    </section>
  );
}

// "ELO per match": every counted match in the range as a sortable table.
// Each column's most useful FIRST direction (second click reverses): dates
// newest-first, matches A→Z by opponent, results wins-first, deltas
// biggest-gain-first (reverse = biggest losses first).
type SortKey = "date" | "match" | "result" | "delta";

// "team" appears only on tournament-bonus rows (team events have no matches).
const discLabel = (d: RatingMover["discipline"]) =>
  d === "team" ? "Team" : DISCIPLINE_LABEL[d] ?? d;
const SORT_DEFAULT_DIR: Record<SortKey, 1 | -1> = {
  date: -1,
  match: 1,
  result: 1,
  delta: -1,
};

function sortMovers(movers: RatingMover[], sort: Sort<SortKey>) {
  const { key, dir } = sort;
  // Bonus rows (match_id null) land at the END of their day in play order.
  const ord = (m: RatingMover) => m.match_id ?? Number.MAX_SAFE_INTEGER;
  const name = (m: RatingMover) => m.bonus_label ?? m.opponent_name ?? "?";
  return [...movers].sort((a, b) => {
    if (key === "date")
      // Same-day ties follow the direction too (ids track entry order).
      return dir * (a.date.localeCompare(b.date) || ord(a) - ord(b));
    if (key === "match") return dir * name(a).localeCompare(name(b), "vi");
    if (key === "result") {
      const rank = (m: RatingMover) => (resultOf(m) === "W" ? 0 : 1);
      // Within the same result, biggest impact first.
      return dir * (rank(a) - rank(b)) || Math.abs(b.delta) - Math.abs(a.delta);
    }
    return dir * (a.delta - b.delta); // delta: -1 dir = biggest gains first
  });
}

export function EloTableCard({ elo }: { elo: RatingBreakdown }) {
  const [sort, setSort] = useState<Sort<SortKey>>({ key: "date", dir: -1 });
  const rows = useMemo(() => sortMovers(elo.movers, sort), [elo.movers, sort]);
  const onSort = (k: SortKey) =>
    setSort((s) => toggleSort(s, k, SORT_DEFAULT_DIR));

  if (elo.rating_end === null) return null;
  return (
    <section className="stats-card">
      <div className="elo-head">
        <h3>📋 ELO per match</h3>
        <span className="elo-note-inline">
          {elo.counted} counted matches in this range
        </span>
      </div>
      {elo.movers.length === 0 ? (
        <p className="stats-muted">No ELO-counted matches in this range.</p>
      ) : (
        <div className="elo-table-wrap">
          <table className="elo-table">
            <thead>
              <tr>
                <SortableTh label="Date" k="date" sort={sort} onSort={onSort} />
                <SortableTh
                  label="Match"
                  k="match"
                  sort={sort}
                  onSort={onSort}
                  title="Sorted by opponent name"
                />
                <SortableTh label="W/L" k="result" sort={sort} onSort={onSort} />
                <SortableTh
                  label="±ELO"
                  k="delta"
                  sort={sort}
                  onSort={onSort}
                  title="First click: biggest gains; second: biggest losses"
                />
              </tr>
            </thead>
            <tbody>
              {rows.map((m) => {
                // Tournament placement bonus — a flat add-on, not a match.
                if (m.match_id === null)
                  return (
                    <tr
                      key={`bonus-${m.date}-${m.bonus_label}`}
                      className="elo-row-bonus"
                    >
                      <td className="elo-td-date">{shortDate(m.date)}</td>
                      <td className="elo-td-match">
                        🏆 {m.bonus_label} ({discLabel(m.discipline)})
                      </td>
                      <td className="elo-td-res">—</td>
                      <td className="elo-td-delta elo-delta-val pos">
                        {fmtDelta(m.delta)}
                      </td>
                    </tr>
                  );
                const r = resultOf(m);
                return (
                  <tr key={m.match_id}>
                    <td className="elo-td-date">{shortDate(m.date)}</td>
                    <td className="elo-td-match">
                      {m.my_sets}-{m.opp_sets} {matchupOf(m)} (
                      {discLabel(m.discipline)})
                    </td>
                    <td
                      className={`elo-td-res ${
                        r === "W" ? "win" : r === "L" ? "loss" : ""
                      }`}
                    >
                      {r}
                    </td>
                    <td
                      className={`elo-td-delta elo-delta-val ${
                        m.delta >= 0 ? "pos" : "neg"
                      }`}
                    >
                      {fmtDelta(m.delta)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
