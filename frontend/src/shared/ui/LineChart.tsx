import { useState } from "react";

// One chart point datum (callers pass structurally-matching literals —
// today only EloCurve builds them).
interface Bar {
  label: string;
  value: number | null; // numeric height driver; null = gap (no dot, no line)
  display: string; // text shown above the bar
  tip?: string; // rich-tooltip heading
}

// A YouTube-style area + line trend chart. SVG draws the gridlines, filled
// area and line (with a 0..100 viewBox stretched to fit); dots, axis labels
// and the hover tooltip are HTML overlays so text never gets distorted by the
// non-uniform scaling. Null values leave a blank gap: the line breaks into
// independent segments around them.
export default function LineChart({
  points,
  formatY,
  gutter,
}: {
  points: Bar[];
  formatY: (v: number) => string;
  // When set (a CSS width), mimic ActivityChart's day-slot layout so this
  // chart's columns line up with a comparison chart above it: y-axis in a
  // left gutter of this width, slot-centred x positions, one x label per
  // slot, no horizontal card padding.
  gutter?: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const n = points.length;
  const vals = points
    .map((p) => p.value)
    .filter((v): v is number => v !== null);
  if (n === 0 || vals.length === 0) return null;
  const max = Math.max(1, ...vals);

  const xAt = (i: number) =>
    gutter ? ((i + 0.5) / n) * 100 : n === 1 ? 50 : (i / (n - 1)) * 100;
  const coords = points.map((p, i) => ({
    x: xAt(i),
    y: p.value === null ? null : 100 - (p.value / max) * 100,
    p,
  }));

  // Consecutive non-null runs become independent line/area segments; nulls
  // in between stay blank.
  const runs: { x: number; y: number }[][] = [[]];
  for (const c of coords) {
    if (c.y === null) {
      if (runs[runs.length - 1].length) runs.push([]);
    } else {
      runs[runs.length - 1].push({ x: c.x, y: c.y });
    }
  }
  const segs = runs.filter((r) => r.length > 1);

  // Show at most ~12 x labels to avoid crowding; in slot mode match
  // ActivityChart's rule so both charts label the same days.
  const labelStep = gutter
    ? n <= 31
      ? 1
      : Math.ceil(n / 16)
    : Math.ceil(n / 12);
  const active = hover === null ? null : coords[hover];

  const yAxis = (
    <div
      className={gutter ? "linechart-yaxis-left" : "linechart-yaxis"}
      style={gutter ? { flexBasis: gutter } : undefined}
    >
      <span>{formatY(max)}</span>
      <span>{formatY(max / 2)}</span>
      <span>{formatY(0)}</span>
    </div>
  );

  return (
    <div className={`linechart${gutter ? " aligned" : ""}`}>
      <div className="linechart-row">
        {gutter && yAxis}
        <div className="linechart-plot" onMouseLeave={() => setHover(null)}>
          <svg viewBox="0 0 100 100" preserveAspectRatio="none">
            {[0, 50, 100].map((y) => (
              <line
                key={y}
                x1="0"
                y1={y}
                x2="100"
                y2={y}
                className="lc-grid"
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {segs.map((seg, si) => (
              <g key={si}>
                <path
                  d={
                    `M ${seg[0].x},100 ` +
                    seg.map((c) => `L ${c.x},${c.y}`).join(" ") +
                    ` L ${seg[seg.length - 1].x},100 Z`
                  }
                  className="lc-area"
                />
                <polyline
                  points={seg.map((c) => `${c.x},${c.y}`).join(" ")}
                  className="lc-line"
                  fill="none"
                  vectorEffect="non-scaling-stroke"
                />
              </g>
            ))}
          </svg>

          {coords.map((c, i) =>
            c.y === null ? null : (
              <div
                key={i}
                className={`lc-dot${hover === i ? " active" : ""}`}
                style={{ left: `${c.x}%`, top: `${c.y}%` }}
              />
            )
          )}

          {/* Invisible vertical hit-bands make hovering easy (blank slots
              have nothing to show, so no band). */}
          {coords.map((c, i) =>
            c.y === null ? null : (
              <div
                key={`h${i}`}
                className="lc-hit"
                style={{ left: `${c.x}%`, width: `${100 / n}%` }}
                onMouseEnter={() => setHover(i)}
              />
            )
          )}

          {active && active.y !== null && (
            <div
              className={`lc-tooltip${active.y < 35 ? " below" : ""}${
                active.x < 15 ? " edge-left" : active.x > 85 ? " edge-right" : ""
              }`}
              style={{ left: `${active.x}%`, top: `${active.y}%` }}
            >
              <div className="lc-tt-date">{active.p.tip ?? active.p.label}</div>
              <div className="lc-tt-value">{active.p.display}</div>
            </div>
          )}
        </div>

        {!gutter && yAxis}
      </div>

      <div
        className="linechart-xaxis"
        style={gutter ? { marginLeft: gutter, marginRight: 0 } : undefined}
      >
        {points.map((p, i) => (
          <span key={i} className="lc-xlabel">
            {i % labelStep === 0 ? p.label : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
