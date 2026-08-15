// "Is the gap closing?" — one thin bar per decided h2h match, oldest →
// newest: set margin (my_sets − opp_sets, +3…−3) up for wins (green) and
// down for losses (red), the app-wide W/L colors. A handicap change is
// marked under the axis at the first match of the new kèo — comparing
// scores only makes sense within one kèo. Hover = full match tooltip.
import { prettyDate } from "../../../shared/dates";
import { hdcLabel } from "../../../shared/matches";
import type { Match } from "../../daily-tracker/types";

const WIN = "#5fa83c";
const LOSS = "#d64545";
const BAR_W = 10;
const GAP = 6;
const PLOT_H = 96; // drawing band for the ±3 margins
const AXIS_H = 30; // room for two staggered rows of kèo-change labels
const PAD = 24; // left gutter for the +3/−3 scale labels
const CHAR_W = 5; // ≈px per character at the 9px axis font — for collision math

function kelo(m: Match): string {
  return hdcLabel(m.handicap, m.handicap_pattern) ?? "even";
}

export default function MarginTimeline({ matches }: { matches: Match[] }) {
  // Oldest → newest, decided only (the caller already filters, belt+braces).
  const ms = matches.filter((m) => m.my_sets !== m.opp_sets);
  if (ms.length < 3) return null; // a chart over 2 points is noise
  const width = PAD + ms.length * (BAR_W + GAP) + 4;
  const mid = PLOT_H / 2;
  const scale = (PLOT_H / 2 - 6) / 3; // px per set of margin
  // Kèo-change labels laid out greedily on two staggered rows so adjacent
  // changes never overprint (they did with back-to-back kèo switches). A
  // change whose label fits neither row keeps its dashed line + tooltip
  // but skips the text.
  const labelRow = new Map<number, number>(); // match index → row 0|1
  const rowEnds = [-Infinity, -Infinity];
  ms.forEach((m, i) => {
    if (i !== 0 && kelo(m) === kelo(ms[i - 1])) return;
    const x = PAD + i * (BAR_W + GAP) - 2;
    const row = rowEnds.findIndex((end) => x >= end);
    if (row !== -1) {
      labelRow.set(i, row);
      rowEnds[row] = x + kelo(m).length * CHAR_W + 6;
    }
  });
  return (
    <div className="tac-chart">
      <div className="tac-chart-title">Set margin per match (old → new)</div>
      <svg
        className="tac-margin-svg"
        viewBox={`0 0 ${width} ${PLOT_H + AXIS_H}`}
        width={width}
        height={PLOT_H + AXIS_H}
        role="img"
        aria-label="Set margin per head-to-head match over time"
      >
        {/* scale hints + baseline */}
        <text x={PAD - 6} y={mid - 3 * scale + 3} className="tac-axis-txt" textAnchor="end">+3</text>
        <text x={PAD - 6} y={mid + 3 * scale + 3} className="tac-axis-txt" textAnchor="end">−3</text>
        <line x1={PAD - 2} y1={mid} x2={width} y2={mid} className="tac-axis-line" />
        {ms.map((m, i) => {
          const margin = m.my_sets - m.opp_sets;
          const h = Math.max(Math.abs(margin) * scale, 3);
          const x = PAD + i * (BAR_W + GAP);
          const y = margin > 0 ? mid - h : mid;
          const won = margin > 0;
          const kChanged = i === 0 || kelo(m) !== kelo(ms[i - 1]);
          return (
            <g key={m.id}>
              <rect
                x={x}
                y={y}
                width={BAR_W}
                height={h}
                rx={2}
                fill={won ? WIN : LOSS}
              >
                <title>
                  {`${prettyDate(m.date)} · ${won ? "W" : "L"} ${m.my_sets}–${m.opp_sets} · ${kelo(m)}${m.event_name ? ` · ${m.event_name}` : ""}`}
                </title>
              </rect>
              {kChanged && (
                <>
                  <line
                    x1={x - GAP / 2}
                    y1={mid - 3 * scale}
                    x2={x - GAP / 2}
                    y2={PLOT_H}
                    className="tac-kelo-line"
                  />
                  {labelRow.has(i) && (
                    <text
                      x={x - 2}
                      y={PLOT_H + 12 + labelRow.get(i)! * 11}
                      className="tac-axis-txt"
                    >
                      {kelo(m)}
                    </text>
                  )}
                </>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
