import type {
  BreakdownBucket,
  RatingBreakdown,
  StatsResponse,
} from "../types";
import { trackerApi } from "../api";
import { fromIso as parseIso, prettyDate, todayIso } from "../../../shared/dates";
import type { Mode, Unit } from "../../../shared/period";
import { chartUnitFor } from "../../../shared/period";
import { useLoad, useMutate } from "../../../shared/useApi";
import ActivityChart from "../../../shared/ui/ActivityChart";
import type { ActivityPoint } from "../../../shared/ui/ActivityChart";
import EloCurve from "../../../shared/ui/EloCurve";
import CoachPackageCard from "./CoachPackageCard";
import { fmtDelta, fmtMinutes } from "../../../shared/format";

const UNIT_TITLE: Record<Unit, string> = {
  month: "by month",
  week: "by week",
  day: "by day",
};

const WD_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];


// Map a breakdown bucket to a composite chart point (all three metrics at once).
function bucketPoint(b: BreakdownBucket): ActivityPoint {
  const range = `${prettyDate(b.date_from)} — ${prettyDate(b.date_to)}`;
  // Rich-tooltip heading: a full date for single days, else the range.
  const tip =
    b.date_from === b.date_to
      ? `${WD_SHORT[parseIso(b.date_from).getDay()]}, ${prettyDate(b.date_from)}`
      : `${b.label} · ${range}`;
  return {
    label: b.label,
    tip,
    minutes: b.minutes,
    matches: b.matches,
    daysPhysical: b.days_physical,
    // Future buckets keep their axis slot but draw nothing (the grid blocks
    // future entry anyway, so they can only ever be zeros).
    blank: b.date_from > todayIso(),
  };
}

// My ELO across the panel's timeline: header answers "how much did I gain or
// lose in this range", the EloCurve shows the rating at each bucket's end
// (quiet buckets carry the value forward; the full bucket list renders so the
// day axis lines up with the comparison chart above — same buckets, same
// gutter, same slot positions). Hidden while the range predates the anchor.
// The rating is GLOBAL — no discipline/category filters apply.
function EloBlock({
  elo,
  unitIsDay,
  gutterPx = 210,
}: {
  elo: RatingBreakdown;
  unitIsDay: boolean;
  gutterPx?: number;
}) {
  if (elo.rating_end === null) return null;
  return (
    <div className="stat-block elo-block">
      <div className="elo-head">
        <h3>📈 ELO</h3>
        <span
          className="elo-current"
          title="Rating at the end of the visible range"
        >
          {elo.rating_end}
        </span>
        <span
          className={`elo-chip ${elo.total_delta >= 0 ? "elo-up" : "elo-down"}`}
          title="Net Δ in the visible range (ELO-counted matches)"
        >
          {fmtDelta(elo.total_delta)} · {elo.counted} matches
        </span>
        {elo.rating_start !== null && elo.rating_start !== elo.rating_end && (
          <span className="elo-endnote">from {elo.rating_start}</span>
        )}
      </div>
      <EloCurve
        elo={elo}
        labelOf={(b) => b.label}
        tipOf={(b) => (b.date_from === b.date_to ? prettyDate(b.date_from) : b.label)}
        gutter={`${unitIsDay ? gutterPx : 46}px`}
      />
    </div>
  );
}

// Analysis panel shown under the grid. The period (mode + range) is shared with
// the grid and passed in as props; only the chart display prefs are local.
export default function AnalysisPanel({
  mode,
  fromIso,
  toIso: rangeToIso,
  label,
  reloadSignal,
  gutterPx,
}: {
  mode: Mode;
  fromIso: string;
  toIso: string;
  label: string;
  reloadSignal: number;
  // Width of the grid's Category column, used to align the chart's day axis.
  gutterPx?: number;
}) {
  const chartUnit: Unit | null = chartUnitFor(mode, "line", fromIso, rangeToIso);
  const rangeValid = fromIso <= rangeToIso;

  // All range-dependent data in one load; useLoad's seq counter drops
  // out-of-order responses (rapid Prev/Prev clicks). reloadSignal changes
  // when the grid data is mutated.
  const { data: ranged, error: loadError } = useLoad<{
    stats: StatsResponse;
    buckets: BreakdownBucket[];
    elo: RatingBreakdown;
  } | null>(async () => {
    if (!rangeValid) return null;
    const [s, b, r] = await Promise.all([
      trackerApi.getStats(fromIso, rangeToIso),
      chartUnit
        ? trackerApi.getBreakdown(fromIso, rangeToIso, chartUnit)
        : Promise.resolve(null),
      // Day granularity even without a chart (single-day mode still shows
      // the "how much did today move me" header).
      trackerApi.ratingBreakdown(fromIso, rangeToIso, chartUnit ?? "day"),
    ]);
    return { stats: s, buckets: b ? b.buckets : [], elo: r };
  }, [rangeValid, fromIso, rangeToIso, chartUnit, reloadSignal]);
  const stats = rangeValid ? ranged?.stats ?? null : null;
  const buckets = (rangeValid && ranged?.buckets) || [];
  const elo = rangeValid ? ranged?.elo ?? null : null;

  // Coaching packages are global (not tied to the selected range); refreshed
  // on mount and after any mutation. Load failures stay silent (the card just
  // doesn't render), like before the useLoad migration.
  const { data: pkgData, setData: setPkgData } = useLoad(
    () => trackerApi.getCoachPackages(),
    [reloadSignal]
  );
  const packages = pkgData?.packages ?? [];
  const { run: runPkg, busy: pkgBusy, error: pkgError } = useMutate();

  // Renew flow: the card's button flags session size+1 as the new package's
  // start; the response already carries the recomputed package list.
  const startNextPackage = async () => {
    const r = await runPkg(() => trackerApi.startNextCoachPackage());
    if (r !== undefined) setPkgData(r);
  };

  const error = !rangeValid
    ? "'From' date is after 'To' date."
    : pkgError ?? loadError;

  return (
    <section className="analysis">
      <div className="analysis-head">
        <h2>📊 Analysis</h2>
        <span className="analysis-range">{label}</span>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {stats && (
        <>
          {/* Comparison chart first — directly under the grid so it can be read
              side-by-side with the day columns above. */}
          {chartUnit && buckets.length > 0 && (
            <div className="stat-block comparison-block">
              <ActivityChart
                points={buckets.map(bucketPoint)}
                formatMinutes={(v) => fmtMinutes(Math.round(v))}
                unitIsDay={chartUnit === "day"}
                gutterPx={gutterPx}
                header={
                  <>
                    <h3>Comparison {UNIT_TITLE[chartUnit]}</h3>
                    <div className="chart-legend">
                      <span className="lg-item">
                        <span className="lg-sw lg-time" />Training time
                      </span>
                      <span className="lg-item">
                        <span className="lg-sw lg-match" />Matches
                      </span>
                      <span className="lg-item">
                        <span className="lg-sw lg-phys" />Physical days
                      </span>
                    </div>
                  </>
                }
              />
            </div>
          )}

          {elo && (
            <EloBlock
              elo={elo}
              unitIsDay={(chartUnit ?? "day") === "day"}
              gutterPx={gutterPx}
            />
          )}

          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-card-title">Days trained</div>
              <div className="stat-big">
                {stats.days_trained}
                <span className="stat-of">/{stats.num_days}</span>
              </div>
              <div className="stat-sub">days with activity</div>
            </div>

            <div className="stat-card">
              <div className="stat-card-title">Physical days</div>
              <div className="stat-big">{stats.days_physical}</div>
              <div className="stat-sub">days with physical training</div>
            </div>

            <div className="stat-card">
              <div className="stat-card-title">Training time</div>
              <div className="stat-big">{fmtMinutes(stats.minutes_total)}</div>
              <div className="stat-sub">total duration logged</div>
            </div>

            <div
              className="stat-card"
              title="Coach + Partner training + 5 min per match set"
            >
              <div className="stat-card-title">🏓 Racket time</div>
              <div className="stat-big">
                {fmtMinutes(stats.racket_minutes_total)}
              </div>
              <div className="stat-sub">time with racket in hand</div>
              <div className="stat-line muted">
                <span>training</span>
                <span>{fmtMinutes(stats.racket_minutes_training)}</span>
              </div>
              <div className="stat-line muted">
                <span>matches (~5m/set)</span>
                <span>{fmtMinutes(stats.racket_minutes_matches)}</span>
              </div>
            </div>

            {/* The Singles/Doubles/All/vs-Pips win-rate cards were removed
                2026-08-02 (user request) — the Profile tab's KPI row owns
                match stats now, with the same drill-down. */}
            {packages.length > 0 && (
              <CoachPackageCard
                current={
                  packages.find((p) => p.is_current) ??
                  packages[packages.length - 1]
                }
                onStartNext={startNextPackage}
                busy={pkgBusy}
              />
            )}
          </div>

        </>
      )}
    </section>
  );
}
