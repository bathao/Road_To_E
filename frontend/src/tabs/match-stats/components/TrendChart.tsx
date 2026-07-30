import { useState } from "react";
import { pct } from "../../../shared/format";
import type { MatchTrendBucket } from "../types";

// Results & form chart. A per-day win RATE is noise at 2-3 matches/day, so
// each bucket instead shows what actually happened — wins as green bars up,
// losses as red bars down from a shared baseline (equal counts = equal
// heights) — while the blue line is the rolling form: win rate of the last
// 10 decided matches, read against the right-hand % axis. Callers pass only
// buckets that had matches; skipped days simply have no bar.
export default function TrendChart({
  buckets,
}: {
  buckets: MatchTrendBucket[];
}) {
  const [hover, setHover] = useState<number | null>(null);
  const n = buckets.length;
  if (n === 0) return null;

  const maxW = Math.max(1, ...buckets.map((b) => b.wins));
  const maxL = Math.max(1, ...buckets.map((b) => b.losses));
  // One shared per-match unit for both directions, so a 2-win bar and a
  // 2-loss bar are the same size; the baseline sits between the two ranges.
  const unit = 100 / (maxW + maxL);
  const base = maxW * unit;

  const xAt = (i: number) => ((i + 0.5) / n) * 100;
  const yForm = (f: number) => 100 - f * 100;

  // Consecutive buckets with a form value become independent line segments
  // (form is null until enough decided matches have been played).
  const runs: { x: number; y: number }[][] = [[]];
  buckets.forEach((b, i) => {
    if (b.form === null) {
      if (runs[runs.length - 1].length) runs.push([]);
    } else {
      runs[runs.length - 1].push({ x: xAt(i), y: yForm(b.form) });
    }
  });
  const segs = runs.filter((r) => r.length > 1);

  const labelStep = Math.ceil(n / 12);
  const active = hover === null ? null : buckets[hover];

  return (
    <div className="trendchart">
      <div className="tc-legend">
        <span>
          <i className="tc-sw tc-sw-win" /> Wins
        </span>
        <span>
          <i className="tc-sw tc-sw-loss" /> Losses
        </span>
        <span>
          <i className="tc-sw tc-sw-form" /> Form (last 10 matches)
        </span>
      </div>

      <div className="tc-row">
        <div className="tc-plot" onMouseLeave={() => setHover(null)}>
          <svg viewBox="0 0 100 100" preserveAspectRatio="none">
            {/* Form gridlines (right % axis) + the W/L baseline. */}
            {[0, 50, 100].map((y) => (
              <line
                key={y}
                x1="0"
                y1={y}
                x2="100"
                y2={y}
                className="tc-grid"
                vectorEffect="non-scaling-stroke"
              />
            ))}
            <line
              x1="0"
              y1={base}
              x2="100"
              y2={base}
              className="tc-baseline"
              vectorEffect="non-scaling-stroke"
            />
            {segs.map((seg, si) => (
              <polyline
                key={si}
                points={seg.map((c) => `${c.x},${c.y}`).join(" ")}
                className="tc-form-line"
                fill="none"
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </svg>

          {/* W/L bars (HTML overlays so widths stay in px, not stretched). */}
          {buckets.map((b, i) => (
            <div key={i}>
              {b.wins > 0 && (
                <div
                  className={`tc-bar tc-bar-win${hover === i ? " active" : ""}`}
                  style={{
                    left: `${xAt(i)}%`,
                    top: `${base - b.wins * unit}%`,
                    height: `${b.wins * unit}%`,
                  }}
                />
              )}
              {b.losses > 0 && (
                <div
                  className={`tc-bar tc-bar-loss${hover === i ? " active" : ""}`}
                  style={{
                    left: `${xAt(i)}%`,
                    top: `${base}%`,
                    height: `${b.losses * unit}%`,
                  }}
                />
              )}
            </div>
          ))}

          {/* Form dots only on hover — the line stays clean otherwise. */}
          {hover !== null && buckets[hover].form !== null && (
            <div
              className="tc-form-dot"
              style={{
                left: `${xAt(hover)}%`,
                top: `${yForm(buckets[hover].form!)}%`,
              }}
            />
          )}

          {/* Invisible hit-bands make hovering easy. */}
          {buckets.map((_, i) => (
            <div
              key={`h${i}`}
              className="tc-hit"
              style={{ left: `${xAt(i)}%`, width: `${100 / n}%` }}
              onMouseEnter={() => setHover(i)}
            />
          ))}

          {active &&
            hover !== null &&
            (() => {
              // Anchor above whichever is higher: the win bar's top or the
              // form dot — the tooltip then never covers either.
              const anchorY = Math.min(
                base - active.wins * unit,
                active.form !== null ? yForm(active.form) : 100
              );
              return (
                <div
                  className={`lc-tooltip${anchorY < 35 ? " below" : ""}${
                    xAt(hover) < 15
                      ? " edge-left"
                      : xAt(hover) > 85
                      ? " edge-right"
                      : ""
                  }`}
                  style={{ left: `${xAt(hover)}%`, top: `${anchorY}%` }}
                >
                  <div className="lc-tt-date">{active.label}</div>
                  <div className="lc-tt-value">
                    {active.wins}-{active.losses}
                    {active.matches - active.wins - active.losses > 0
                      ? `-${active.matches - active.wins - active.losses}`
                      : ""}{" "}
                    · {active.matches} match{active.matches === 1 ? "" : "es"}
                  </div>
                  {active.form !== null && (
                    <div className="tc-tt-form">
                      Form (last 10): <b>{pct(active.form)}</b>
                    </div>
                  )}
                </div>
              );
            })()}
        </div>

        {/* Right axis reads the FORM line (0-100%); bar heights are counts
            and are read from the tooltip instead. */}
        <div className="tc-yaxis">
          <span>100%</span>
          <span>50%</span>
          <span>0%</span>
        </div>
      </div>

      <div className="tc-xaxis">
        {buckets.map((b, i) => (
          <span key={i} className="tc-xlabel">
            {i % labelStep === 0 ? b.label : ""}
          </span>
        ))}
      </div>
    </div>
  );
}
