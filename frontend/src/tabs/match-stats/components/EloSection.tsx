import type { RatingBreakdown, RatingBucket, RatingMover } from "../types";

// "ELO theo thời gian": net ±Δ per bucket + the range's most influential
// matches. GLOBAL — the rating ignores the tab's discipline/category filters
// (a filtered "rating at end of bucket" would lie), and the section says so.

const DISCIPLINE_VI: Record<string, string> = {
  singles: "đơn",
  doubles: "đôi",
  one_v_two: "1v2",
  two_v_one: "2v1",
};

function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

function fmtDelta(d: number): string {
  return `${d > 0 ? "+" : ""}${d.toFixed(1)}`;
}

// Signed horizontal bars around a center zero line — one row per bucket that
// actually had counted matches (quiet buckets are noise here).
function DeltaBars({ buckets }: { buckets: RatingBucket[] }) {
  const shown = buckets.filter((b) => b.counted > 0);
  if (!shown.length) {
    return <p className="stats-muted">Chưa có trận tính ELO trong khoảng này.</p>;
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
              · {b.counted} trận · cuối {b.rating_end}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

function MoverLine({ m }: { m: RatingMover }) {
  const res = m.my_sets > m.opp_sets ? "thắng" : "thua";
  return (
    <li className="elo-mover">
      <span className={`elo-delta-val ${m.delta >= 0 ? "pos" : "neg"}`}>
        {fmtDelta(m.delta)}
      </span>
      <span className="elo-mover-desc">
        {res} {m.my_sets}-{m.opp_sets} vs {m.opponent_name ?? "?"} (
        {DISCIPLINE_VI[m.discipline] ?? m.discipline})
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
  const unitVi = unit === "month" ? "tháng" : unit === "week" ? "tuần" : "ngày";
  return (
    <section className="stats-card elo-section">
      <div className="elo-head">
        <h3>📈 ELO theo thời gian</h3>
        <span
          className={`elo-chip ${elo.total_delta >= 0 ? "elo-up" : "elo-down"}`}
          title="Δ ròng trong khoảng đang xem"
        >
          {fmtDelta(elo.total_delta)} · {elo.counted} trận
        </span>
        <span className="elo-endnote">
          {elo.rating_start !== null && elo.rating_start !== elo.rating_end
            ? `${elo.rating_start} → `
            : ""}
          <b>{elo.rating_end}</b> · tính trên MỌI trận đã tính ELO — không theo 2
          bộ lọc phía trên
        </span>
      </div>
      <div className="elo-cols">
        <div>
          <h4>Δ theo {unitVi}</h4>
          <DeltaBars buckets={elo.buckets} />
        </div>
        <div>
          <h4>Trận ảnh hưởng nhất</h4>
          {elo.top_gains.length + elo.top_losses.length === 0 ? (
            <p className="stats-muted">Chưa có trận tính ELO trong khoảng này.</p>
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
