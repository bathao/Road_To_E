import { useCallback, useEffect, useState } from "react";
import type {
  BreakdownBucket,
  CoachPackage,
  MatchStats,
  StatsResponse,
} from "../types";
import { trackerApi } from "../api";
import { fromIso as parseIso, prettyDate } from "../../../shared/dates";
import type { Mode, Unit } from "../../../shared/period";
import { chartUnitFor } from "../../../shared/period";
import BarChart from "../../../shared/ui/BarChart";
import type { Bar } from "../../../shared/ui/BarChart";
import LineChart from "../../../shared/ui/LineChart";
import { fmtMinutes, pct } from "../../../shared/format";

// Metrics the comparison chart can plot.
type MetricKey =
  | "minutes"
  | "matches"
  | "wins"
  | "win_rate"
  | "days_trained"
  | "days_physical";

const METRICS: { key: MetricKey; label: string }[] = [
  { key: "minutes", label: "Training time" },
  { key: "matches", label: "Matches" },
  { key: "wins", label: "Wins" },
  { key: "win_rate", label: "Win rate" },
  { key: "days_trained", label: "Days trained" },
  { key: "days_physical", label: "Physical days" },
];

const UNIT_TITLE: Record<Unit, string> = {
  month: "by month",
  week: "by week",
  day: "by day",
};

const WD_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];


// Map a breakdown bucket to a chart bar for the chosen metric.
function bucketBar(b: BreakdownBucket, metric: MetricKey): Bar {
  const range = `${prettyDate(b.date_from)} — ${prettyDate(b.date_to)}`;
  // Rich-tooltip heading: a full date for single days, else the range.
  const tip =
    b.date_from === b.date_to
      ? `${WD_SHORT[parseIso(b.date_from).getDay()]}, ${prettyDate(b.date_from)}`
      : `${b.label} · ${range}`;
  let value: number;
  let display: string;
  switch (metric) {
    case "minutes":
      value = b.minutes;
      display = fmtMinutes(b.minutes);
      break;
    case "matches":
      value = b.matches;
      display = String(b.matches);
      break;
    case "wins":
      value = b.wins;
      display = `${b.wins}W`;
      break;
    case "win_rate":
      value = b.win_rate === null ? 0 : Math.round(b.win_rate * 100);
      display = pct(b.win_rate);
      break;
    case "days_trained":
      value = b.days_trained;
      display = String(b.days_trained);
      break;
    case "days_physical":
      value = b.days_physical;
      display = String(b.days_physical);
      break;
  }
  return { label: b.label, value, display, title: `${b.label} · ${range}`, tip };
}

// A summary card for one discipline (or overall).
function MatchCard({ title, s }: { title: string; s: MatchStats }) {
  return (
    <div className="stat-card">
      <div className="stat-card-title">{title}</div>
      <div className="stat-big">{pct(s.win_rate)}</div>
      <div className="stat-sub">win rate</div>
      <div className="stat-line">
        <span>{s.total} matches</span>
        <span>
          <b className="win">{s.wins}W</b> · <b className="loss">{s.losses}L</b>
          {s.ties ? ` · ${s.ties}T` : ""}
        </span>
      </div>
      <div className="stat-line muted">
        <span>sets</span>
        <span>
          {s.sets_won}–{s.sets_lost}
        </span>
      </div>
    </div>
  );
}

function pkgStatusText(p: CoachPackage): string {
  switch (p.status) {
    case "low":
      return `Almost out — ${p.remaining} session${p.remaining === 1 ? "" : "s"} left, renew soon`;
    case "done":
      return "Package used up — time to renew";
    case "over":
      return `Trained ${p.used} (over ${p.size}) — mark the new package's start?`;
    default:
      return `${p.remaining} session${p.remaining === 1 ? "" : "s"} left`;
  }
}

// Coaching package (10-session block) status: how many sessions are left in the
// current package. Range-independent — it's about "now".
function CoachPackageCard({ current }: { current: CoachPackage }) {
  return (
    <div className={`stat-card pkg-card pkg-${current.status}`}>
      <div className="stat-card-title">Coach package</div>
      <div className="stat-big">
        {current.used}
        <span className="stat-of">/{current.size}</span>
      </div>
      <div className="stat-sub">started {prettyDate(current.start_date)}</div>
      <div className="pkg-status">{pkgStatusText(current)}</div>
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
}: {
  mode: Mode;
  fromIso: string;
  toIso: string;
  label: string;
  reloadSignal: number;
}) {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [buckets, setBuckets] = useState<BreakdownBucket[]>([]);
  const [packages, setPackages] = useState<CoachPackage[]>([]);
  const [metric, setMetric] = useState<MetricKey>("minutes");
  const [chartType, setChartType] = useState<"bar" | "line">("line");
  const [error, setError] = useState<string | null>(null);

  const chartUnit: Unit | null = chartUnitFor(
    mode,
    chartType,
    fromIso,
    rangeToIso
  );

  const load = useCallback(async () => {
    if (fromIso > rangeToIso) {
      setError("'From' date is after 'To' date.");
      setStats(null);
      setBuckets([]);
      return;
    }
    try {
      setError(null);
      const [s, b] = await Promise.all([
        trackerApi.getStats(fromIso, rangeToIso),
        chartUnit
          ? trackerApi.getBreakdown(fromIso, rangeToIso, chartUnit)
          : Promise.resolve(null),
      ]);
      setStats(s);
      setBuckets(b ? b.buckets : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [fromIso, rangeToIso, chartUnit]);

  useEffect(() => {
    void load();
    // reloadSignal changes when the grid data is mutated.
  }, [load, reloadSignal]);

  // Coaching packages are global (not tied to the selected range); refresh them
  // on mount and after any mutation.
  useEffect(() => {
    let alive = true;
    trackerApi
      .getCoachPackages()
      .then((r) => {
        if (alive) setPackages(r.packages);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [reloadSignal]);

  return (
    <section className="analysis">
      <div className="analysis-head">
        <h2>📊 Analysis</h2>
        <span className="analysis-range">{label}</span>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}

      {stats && (
        <>
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

            <MatchCard title="Singles" s={stats.singles} />
            <MatchCard title="Doubles" s={stats.doubles} />
            <MatchCard title="All matches" s={stats.overall} />
            <MatchCard title="🏓 vs Pips" s={stats.vs_pips} />

            {packages.length > 0 && (
              <CoachPackageCard
                current={
                  packages.find((p) => p.is_current) ??
                  packages[packages.length - 1]
                }
              />
            )}
          </div>

          {/* Comparison chart: sub-periods of the selected range */}
          {chartUnit && buckets.length > 0 && (
            <div className="stat-block">
              <div className="comparison-head">
                <div className="comparison-title">
                  <h3>Comparison {UNIT_TITLE[chartUnit]}</h3>
                  <div className="seg">
                    <button
                      className={`seg-btn${chartType === "bar" ? " active" : ""}`}
                      onClick={() => setChartType("bar")}
                    >
                      ▦ Columns
                    </button>
                    <button
                      className={`seg-btn${chartType === "line" ? " active" : ""}`}
                      onClick={() => setChartType("line")}
                    >
                      📈 Line
                    </button>
                  </div>
                </div>
                <div className="seg metric-seg">
                  {METRICS.map((m) => (
                    <button
                      key={m.key}
                      className={`seg-btn${metric === m.key ? " active" : ""}`}
                      onClick={() => setMetric(m.key)}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>
              {chartType === "bar" ? (
                <BarChart bars={buckets.map((b) => bucketBar(b, metric))} />
              ) : (
                <LineChart
                  points={buckets.map((b) => bucketBar(b, metric))}
                  formatY={(v) =>
                    metric === "minutes"
                      ? fmtMinutes(Math.round(v))
                      : metric === "win_rate"
                        ? `${Math.round(v)}%`
                        : String(Math.round(v))
                  }
                />
              )}
            </div>
          )}

          {/* Minutes by training category */}
          <div className="stat-block">
            <h3>Training time by category</h3>
            <div className="minutes-bars">
              {stats.minutes_by_category.map((c) => {
                const max = Math.max(
                  1,
                  ...stats.minutes_by_category.map((x) => x.minutes)
                );
                return (
                  <div key={c.key} className="minutes-row">
                    <span className="minutes-label">{c.label}</span>
                    <div className="minutes-track">
                      <div
                        className="minutes-fill"
                        style={{ width: `${(c.minutes / max) * 100}%` }}
                      />
                    </div>
                    <span className="minutes-val">{fmtMinutes(c.minutes)}</span>
                  </div>
                );
              })}
            </div>
          </div>

        </>
      )}
    </section>
  );
}
