// W/L per handicap level ("at what kèo do I compete?") — one row per kèo,
// win/loss segments sized by COUNT with the counts written out (percentages
// on n=2 mislead; h2h samples are small). Div-based: horizontal bars need no
// SVG. Rows keep first-seen (chronological) order — the kèo story reads
// top-down like the timeline.
import { hdcLabel } from "../../../shared/matches";
import type { Match } from "../../daily-tracker/types";

export default function HandicapBars({ matches }: { matches: Match[] }) {
  const ms = matches.filter((m) => m.my_sets !== m.opp_sets);
  if (ms.length < 3) return null;
  const rows: { label: string; w: number; l: number }[] = [];
  const byLabel = new Map<string, { label: string; w: number; l: number }>();
  for (const m of ms) {
    const label = hdcLabel(m.handicap, m.handicap_pattern) ?? "even";
    let row = byLabel.get(label);
    if (!row) {
      row = { label, w: 0, l: 0 };
      byLabel.set(label, row);
      rows.push(row);
    }
    if (m.my_sets > m.opp_sets) row.w += 1;
    else row.l += 1;
  }
  if (rows.length < 2) return null; // one kèo only → the tiles already say it
  const max = Math.max(...rows.map((r) => r.w + r.l));
  return (
    <div className="tac-chart">
      <div className="tac-chart-title">W/L by handicap</div>
      {rows.map((r) => (
        <div key={r.label} className="tac-hdc-row">
          <span className="tac-hdc-label">{r.label}</span>
          <span className="tac-hdc-bar" aria-hidden="true">
            {r.w > 0 && (
              <span
                className="tac-hdc-win"
                style={{ width: `${(r.w / max) * 100}%` }}
              />
            )}
            {r.l > 0 && (
              <span
                className="tac-hdc-loss"
                style={{ width: `${(r.l / max) * 100}%` }}
              />
            )}
          </span>
          <span className="tac-hdc-count">
            {r.w}W–{r.l}L
          </span>
        </div>
      ))}
    </div>
  );
}
