import { useState, type ReactNode } from "react";

// One bucket of the comparison range, carrying all three activity metrics at
// once so they can be read together without switching views.
export interface ActivityPoint {
  label: string; // x-axis label
  tip?: string; // rich-tooltip heading (full date / range)
  minutes: number; // training time
  matches: number; // matches played
  daysPhysical: number; // physical-training days (0/1 at day granularity)
  blank?: boolean; // future bucket: keep the axis slot but draw nothing
}

// A composite activity chart. The three metrics have incompatible units, so
// each is drawn in the form that fits it on a SHARED time axis:
//   • Training time → filled area + line (left "hours" axis, the dominant signal)
//   • Matches       → thin line + dots (right "count" axis)
//   • Physical days → a strip of squares below the plot (filled = trained that
//                     day; shaded by count for week/month buckets)
// A single hover band per bucket surfaces all three values together.
// Blank (future) buckets keep their axis slot but stay empty — the lines
// simply stop at the last real bucket.
//
// Day positions match the Daily-Tracker grid above: a `gutterPx` left column
// (mirroring the grid's "Category" column) and each day centred in an equal
// slot, so a chart point sits directly under that day's grid column and the
// user can glance up to read the day's detail.
export default function ActivityChart({
  points,
  formatMinutes,
  unitIsDay,
  gutterPx = 210,
  header,
}: {
  points: ActivityPoint[];
  formatMinutes: (v: number) => string;
  unitIsDay: boolean;
  gutterPx?: number;
  // Optional title/legend row rendered inside the card, above the plot, so the
  // whole thing reads as one cohesive widget.
  header?: ReactNode;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const n = points.length;
  const real = points.filter((p) => !p.blank);

  const maxMin = Math.max(1, ...real.map((p) => p.minutes));
  const maxCount = Math.max(1, ...real.map((p) => p.matches));
  const maxPhys = Math.max(1, ...real.map((p) => p.daysPhysical));

  // Each day owns an equal-width slot and sits at its centre — same model as
  // the grid's fixed-layout day columns, so positions line up vertically.
  const xAt = (i: number) => ((i + 0.5) / n) * 100;
  const yMin = (v: number) => 100 - (v / maxMin) * 100;
  const yCount = (v: number) => 100 - (v / maxCount) * 100;

  // Runs of consecutive non-blank indices → independent line/area segments
  // (in practice one run ending today, but the code doesn't care).
  const runs: number[][] = [[]];
  points.forEach((p, i) => {
    if (p.blank) {
      if (runs[runs.length - 1].length) runs.push([]);
    } else {
      runs[runs.length - 1].push(i);
    }
  });
  const segs = runs.filter((r) => r.length > 1);

  // Label every day when the count is grid-sized; thin out only for long spans.
  const labelStep = n <= 31 ? 1 : Math.ceil(n / 16);
  const active = hover;
  // In per-day mode, match the grid's measured Category-column width so day
  // points line up under their grid columns; otherwise just a slim hours axis.
  const gutter = `${unitIsDay ? gutterPx : 46}px`;

  return (
    <div className="actchart">
      {header && <div className="actchart-head">{header}</div>}
      <div className="actchart-body">
        {/* Left "hours" axis, right-aligned against the plot (mirrors the
            grid's Category column so the day region starts at the same x). */}
        <div className="actchart-yaxis-left" style={{ flexBasis: gutter }}>
          <span>{formatMinutes(maxMin)}</span>
          <span>{formatMinutes(maxMin / 2)}</span>
          <span>{formatMinutes(0)}</span>
        </div>

        <div className="actchart-plot" onMouseLeave={() => setHover(null)}>
          <svg viewBox="0 0 100 100" preserveAspectRatio="none">
            {[0, 50, 100].map((y) => (
              <line
                key={y}
                x1="0"
                y1={y}
                x2="100"
                y2={y}
                className="ac-grid"
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {segs.map((seg, si) => {
              const time = seg.map(
                (i) => `${xAt(i)},${yMin(points[i].minutes)}`
              );
              return (
                <g key={si}>
                  <path
                    d={
                      `M ${xAt(seg[0])},100 ` +
                      time.map((c) => `L ${c}`).join(" ") +
                      ` L ${xAt(seg[seg.length - 1])},100 Z`
                    }
                    className="ac-area"
                  />
                  <polyline
                    points={time.join(" ")}
                    className="ac-line ac-time"
                    fill="none"
                    vectorEffect="non-scaling-stroke"
                  />
                  <polyline
                    points={seg
                      .map((i) => `${xAt(i)},${yCount(points[i].matches)}`)
                      .join(" ")}
                    className="ac-line ac-match"
                    fill="none"
                    vectorEffect="non-scaling-stroke"
                  />
                </g>
              );
            })}
          </svg>

          {/* Time dots */}
          {points.map((p, i) =>
            p.blank ? null : (
              <div
                key={`t${i}`}
                className={`ac-dot ac-dot-time${hover === i ? " active" : ""}`}
                style={{ left: `${xAt(i)}%`, top: `${yMin(p.minutes)}%` }}
              />
            )
          )}
          {/* Match dots (only where there were matches, to avoid baseline noise) */}
          {points.map((p, i) =>
            !p.blank && p.matches > 0 ? (
              <div
                key={`m${i}`}
                className={`ac-dot ac-dot-match${hover === i ? " active" : ""}`}
                style={{ left: `${xAt(i)}%`, top: `${yCount(p.matches)}%` }}
              />
            ) : null
          )}

          {/* Right "count" axis pinned at the plot's right edge (overlay so it
              doesn't steal width and break the grid alignment). */}
          <div className="actchart-yaxis-right">
            <span>{maxCount}</span>
            <span>{Math.round(maxCount / 2)}</span>
            <span>0</span>
          </div>

          {/* Invisible vertical hit-bands make hovering easy (blank buckets
              have nothing to show, so no band). */}
          {points.map((p, i) =>
            p.blank ? null : (
              <div
                key={`h${i}`}
                className="ac-hit"
                style={{ left: `${xAt(i)}%`, width: `${100 / n}%` }}
                onMouseEnter={() => setHover(i)}
              />
            )
          )}

          {active !== null && (
            <div
              className={`ac-tooltip${yMin(points[active].minutes) < 35 ? " below" : ""}`}
              style={{
                left: `${xAt(active)}%`,
                top: `${yMin(points[active].minutes)}%`,
              }}
            >
              <div className="ac-tt-date">
                {points[active].tip ?? points[active].label}
              </div>
              <div className="ac-tt-row">
                <span className="ac-sw ac-sw-time" />
                Training time
                <b>{formatMinutes(points[active].minutes)}</b>
              </div>
              <div className="ac-tt-row">
                <span className="ac-sw ac-sw-match" />
                Matches
                <b>{points[active].matches}</b>
              </div>
              <div className="ac-tt-row">
                <span className="ac-sw ac-sw-phys" />
                Physical
                <b>
                  {unitIsDay
                    ? points[active].daysPhysical > 0
                      ? "yes"
                      : "no"
                    : `${points[active].daysPhysical} day${points[active].daysPhysical === 1 ? "" : "s"}`}
                </b>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Physical-days strip: one cell per bucket, aligned under the plot
          (blank buckets keep an inert cell so columns stay aligned). */}
      <div className="actchart-strip" style={{ marginLeft: gutter }}>
        {points.map((p, i) => {
          if (p.blank) return <div key={`s${i}`} className="ac-cell" />;
          const on = p.daysPhysical > 0;
          const intensity = on ? 0.35 + 0.65 * (p.daysPhysical / maxPhys) : 0;
          return (
            <div
              key={`s${i}`}
              className={`ac-cell${hover === i ? " active" : ""}`}
              title={
                unitIsDay
                  ? on
                    ? "Physical training"
                    : "No physical training"
                  : `${p.daysPhysical} physical day${p.daysPhysical === 1 ? "" : "s"}`
              }
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
            >
              <span
                className="ac-cell-fill"
                style={on ? { opacity: intensity } : undefined}
              />
            </div>
          );
        })}
      </div>

      <div className="actchart-xaxis" style={{ marginLeft: gutter }}>
        {points.map((p, i) => (
          <span key={i} className="ac-xlabel">
            {i % labelStep === 0 ? p.label : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
