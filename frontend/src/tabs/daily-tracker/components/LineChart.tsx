import { useState } from "react";
import type { Bar } from "./BarChart";

// A YouTube-style area + line trend chart. SVG draws the gridlines, filled
// area and line (with a 0..100 viewBox stretched to fit); dots, axis labels
// and the hover tooltip are HTML overlays so text never gets distorted by the
// non-uniform scaling.
export default function LineChart({
  points,
  formatY,
}: {
  points: Bar[];
  formatY: (v: number) => string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const n = points.length;
  const max = Math.max(1, ...points.map((p) => p.value));

  const coords = points.map((p, i) => ({
    x: n === 1 ? 50 : (i / (n - 1)) * 100,
    y: 100 - (p.value / max) * 100,
    p,
  }));

  const linePts = coords.map((c) => `${c.x},${c.y}`).join(" ");
  const area =
    `M ${coords[0].x},100 ` +
    coords.map((c) => `L ${c.x},${c.y}`).join(" ") +
    ` L ${coords[n - 1].x},100 Z`;

  // Show at most ~12 x labels to avoid crowding.
  const labelStep = Math.ceil(n / 12);
  const active = hover === null ? null : coords[hover];

  return (
    <div className="linechart">
      <div className="linechart-row">
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
            <path d={area} className="lc-area" />
            <polyline
              points={linePts}
              className="lc-line"
              fill="none"
              vectorEffect="non-scaling-stroke"
            />
          </svg>

          {coords.map((c, i) => (
            <div
              key={i}
              className={`lc-dot${hover === i ? " active" : ""}`}
              style={{ left: `${c.x}%`, top: `${c.y}%` }}
            />
          ))}

          {/* Invisible vertical hit-bands make hovering easy. */}
          {coords.map((c, i) => (
            <div
              key={`h${i}`}
              className="lc-hit"
              style={{ left: `${c.x}%`, width: `${100 / Math.max(1, n)}%` }}
              onMouseEnter={() => setHover(i)}
            />
          ))}

          {active && (
            <div
              className={`lc-tooltip${active.y < 35 ? " below" : ""}`}
              style={{ left: `${active.x}%`, top: `${active.y}%` }}
            >
              <div className="lc-tt-date">{active.p.tip ?? active.p.label}</div>
              <div className="lc-tt-value">{active.p.display}</div>
            </div>
          )}
        </div>

        <div className="linechart-yaxis">
          <span>{formatY(max)}</span>
          <span>{formatY(max / 2)}</span>
          <span>{formatY(0)}</span>
        </div>
      </div>

      <div className="linechart-xaxis">
        {points.map((p, i) => (
          <span key={i} className="lc-xlabel">
            {i % labelStep === 0 ? p.label : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
