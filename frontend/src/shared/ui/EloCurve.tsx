// The since-anchor ELO curve — ONE engine for every tab that draws the rating
// over time (Daily Tracker Analysis + Profile). Same semantics everywhere:
// full bucket axis (real time), pre-anchor buckets flat at the anchor value,
// future buckets blank. LineChart scales 0..max, which would flatten a curve
// hovering around ~950 — so values are re-based near the observed min and
// formatY maps gridline values back to real ratings.
import type { ReactNode } from "react";
import { todayIso } from "../dates";
import { fmtDelta } from "../format";
import LineChart from "./LineChart";

// Structural subset of the backend's RatingBucketOut — every tab's
// RatingBreakdown satisfies it.
export interface EloCurveBucket {
  label: string;
  date_from: string;
  date_to: string;
  delta: number;
  counted: number;
  rating_end: number | null;
}

export interface EloCurveData {
  anchor_points: number;
  buckets: EloCurveBucket[];
}

export default function EloCurve({
  elo,
  labelOf,
  tipOf,
  gutter,
  fallback = null,
}: {
  elo: EloCurveData;
  labelOf: (b: EloCurveBucket) => string;
  tipOf: (b: EloCurveBucket) => string;
  gutter?: string;
  /** Rendered instead of the chart when there are <2 drawable points. */
  fallback?: ReactNode;
}) {
  const today = todayIso();
  // ?? null keeps an old backend (field missing) on the previous blank look.
  const anchorVal: number | null = elo.anchor_points ?? null;
  const valueOf = (b: EloCurveBucket): number | null =>
    b.date_from > today ? null : b.rating_end ?? anchorVal;
  const drawn = elo.buckets.map(valueOf).filter((v): v is number => v !== null);
  if (drawn.length < 2) return <>{fallback}</>;
  const base = Math.min(...drawn) - 20;
  return (
    <LineChart
      points={elo.buckets.map((b) => {
        const v = valueOf(b);
        return {
          label: labelOf(b),
          value: v === null ? null : v - base,
          display:
            b.rating_end === null
              ? `${anchorVal} · before anchor`
              : b.counted
                ? `${b.rating_end} · Δ ${fmtDelta(b.delta)} (${b.counted} matches)`
                : String(b.rating_end),
          tip: tipOf(b),
        };
      })}
      formatY={(v) => String(Math.round(v + base))}
      gutter={gutter}
    />
  );
}
