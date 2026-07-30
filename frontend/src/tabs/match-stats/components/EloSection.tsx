import { shortDate } from "../../../shared/dates";
import { DISCIPLINE_LABEL } from "../../../shared/disciplines";
import { fmtDelta } from "../../../shared/format";
import { resultOf } from "../../../shared/types";
import EloCurve from "../../../shared/ui/EloCurve";
import type { RatingBreakdown, RatingMover } from "../types";

// "ELO over time": the SAME rating curve the Daily Tracker and Profile draw
// (shared/ui/EloCurve — one mental model app-wide; the old center-zero
// delta bars confused the user), plus the range's most influential matches.
// GLOBAL — the rating ignores the tab's discipline/category filters (a
// filtered "rating at end of bucket" would lie), and the section says so.

function MoverLine({ m }: { m: RatingMover }) {
  const res = resultOf(m) === "W" ? "win" : "loss";
  return (
    <li className="elo-mover">
      <span className={`elo-delta-val ${m.delta >= 0 ? "pos" : "neg"}`}>
        {fmtDelta(m.delta)}
      </span>
      <span className="elo-mover-desc">
        {res} {m.my_sets}-{m.opp_sets} vs {m.opponent_name ?? "?"} (
        {DISCIPLINE_LABEL[m.discipline] ?? m.discipline})
      </span>
      <span className="elo-mover-date">{shortDate(m.date)}</span>
    </li>
  );
}

export default function EloSection({
  elo,
  unit,
}: {
  elo: RatingBreakdown;
  unit: "month" | "week" | "day";
}) {
  // The whole range predates the anchor — no rating existed yet.
  if (elo.rating_end === null) return null;
  return (
    <section className="stats-card elo-section">
      <div className="elo-head">
        <h3>📈 ELO over time</h3>
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
        <span className="elo-endnote">
          {elo.rating_start !== null && elo.rating_start !== elo.rating_end
            ? `from ${elo.rating_start} · `
            : ""}
          computed over ALL ELO-counted matches — not affected by the two
          filters above
        </span>
      </div>
      <div className="elo-cols">
        <div>
          <h4>ELO curve (by {unit})</h4>
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
        </div>
        <div>
          <h4>Biggest movers</h4>
          {elo.top_gains.length + elo.top_losses.length === 0 ? (
            <p className="stats-muted">No ELO-counted matches in this range.</p>
          ) : (
            <ul className="elo-movers">
              {/* Top 3 gains + top 3 losses, ONE list ranked by absolute
                  impact — gains-then-losses used to read as "the biggest
                  deduction is missing" when a small +Δ sat above a bigger −Δ. */}
              {[...elo.top_gains, ...elo.top_losses]
                .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
                .map((m) => (
                  <MoverLine key={m.match_id} m={m} />
                ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
