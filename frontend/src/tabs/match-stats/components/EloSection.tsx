import { shortDate } from "../../../shared/dates";
import { DISCIPLINE_LABEL } from "../../../shared/disciplines";
import { fmtDelta } from "../../../shared/format";
import { resultOf } from "../../../shared/types";
import type { RatingBreakdown, RatingBucket, RatingMover } from "../types";

// "ELO over time": net ±Δ per bucket + the range's most influential
// matches. GLOBAL — the rating ignores the tab's discipline/category filters
// (a filtered "rating at end of bucket" would lie), and the section says so.

// Signed horizontal bars around a center zero line — one row per bucket that
// actually had counted matches (quiet buckets are noise here).
function DeltaBars({ buckets }: { buckets: RatingBucket[] }) {
  const shown = buckets.filter((b) => b.counted > 0);
  if (!shown.length) {
    return <p className="stats-muted">No ELO-counted matches in this range.</p>;
  }
  const maxAbs = Math.max(1, ...shown.map((b) => Math.abs(b.delta)));
  return (
    <div className="elo-delta-rows">
      {shown.map((b) => (
        <div className="elo-delta-row" key={b.key}>
          <span className="elo-delta-label">{b.label}</span>
          <div className="elo-delta-track">
            {b.delta >= 0 ? (
              <div
                className="elo-delta-fill pos"
                style={{ left: "50%", width: `${(b.delta / maxAbs) * 50}%` }}
              />
            ) : (
              <div
                className="elo-delta-fill neg"
                style={{ right: "50%", width: `${(-b.delta / maxAbs) * 50}%` }}
              />
            )}
          </div>
          <span className={`elo-delta-val ${b.delta >= 0 ? "pos" : "neg"}`}>
            {fmtDelta(b.delta)}
            <span className="elo-delta-n">
              {" "}
              · {b.counted} matches · period end {b.rating_end}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

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
          className={`elo-chip ${elo.total_delta >= 0 ? "elo-up" : "elo-down"}`}
          title="net Δ in the range being viewed"
        >
          {fmtDelta(elo.total_delta)} · {elo.counted} matches
        </span>
        <span className="elo-endnote">
          {elo.rating_start !== null && elo.rating_start !== elo.rating_end
            ? `${elo.rating_start} → `
            : ""}
          <b>{elo.rating_end}</b> · computed over ALL ELO-counted matches — not
          affected by the two filters above
        </span>
      </div>
      <div className="elo-cols">
        <div>
          <h4>Δ by {unit}</h4>
          <DeltaBars buckets={elo.buckets} />
        </div>
        <div>
          <h4>Biggest movers</h4>
          {elo.top_gains.length + elo.top_losses.length === 0 ? (
            <p className="stats-muted">No ELO-counted matches in this range.</p>
          ) : (
            <ul className="elo-movers">
              {elo.top_gains.map((m) => (
                <MoverLine key={`g${m.match_id}`} m={m} />
              ))}
              {elo.top_losses.map((m) => (
                <MoverLine key={`l${m.match_id}`} m={m} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
