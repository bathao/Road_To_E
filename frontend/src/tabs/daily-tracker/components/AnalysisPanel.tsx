import { useCallback, useEffect, useRef, useState } from "react";
import type {
  BreakdownBucket,
  CoachPackage,
  MatchStats,
  RatingBreakdown,
  StatsResponse,
} from "../types";
import { trackerApi } from "../api";
import { fromIso as parseIso, prettyDate, todayIso } from "../../../shared/dates";
import type { Mode, Unit } from "../../../shared/period";
import { chartUnitFor } from "../../../shared/period";
import ActivityChart from "../../../shared/ui/ActivityChart";
import type { ActivityPoint } from "../../../shared/ui/ActivityChart";
import LineChart from "../../../shared/ui/LineChart";
import StatMatchesModal from "./StatMatchesModal";
import type { ResultFilter, StatBucket } from "./StatMatchesModal";
import { fmtMinutes, pct } from "../../../shared/format";

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

// A summary card for one discipline (or overall). The whole card opens the
// drill-down list; clicking the W / L count opens it pre-filtered to just
// those matches.
function MatchCard({
  title,
  s,
  onOpen,
}: {
  title: string;
  s: MatchStats;
  onOpen: (result: ResultFilter) => void;
}) {
  const openOnly = (result: ResultFilter) => (e: React.MouseEvent) => {
    e.stopPropagation();
    onOpen(result);
  };
  return (
    <div
      className="stat-card clickable"
      title="Click to see the matches behind these numbers"
      onClick={() => onOpen("all")}
    >
      <div className="stat-card-title">{title}</div>
      <div className="stat-big">{pct(s.win_rate)}</div>
      <div className="stat-sub">win rate</div>
      <div className="stat-line">
        <span>{s.total} matches</span>
        <span>
          <b className="win smm-open" onClick={openOnly("W")}>
            {s.wins}W
          </b>{" "}
          ·{" "}
          <b className="loss smm-open" onClick={openOnly("L")}>
            {s.losses}L
          </b>
          {s.ties ? ` · ${s.ties}T` : ""}
        </span>
      </div>
    </div>
  );
}

// My ELO across the panel's timeline: header answers "how much did I gain or
// lose in this range", the line shows the rating at each bucket's end (quiet
// buckets carry the value forward). Hidden while the range predates the
// anchor. The rating is GLOBAL — no discipline/category filters apply.
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
  // Pre-anchor buckets draw FLAT at the anchor value (no rating existed yet);
  // future ones only carry today's value forward, so they stay BLANK. The
  // full bucket list still renders so the day axis lines up with the
  // comparison chart above (same buckets, same gutter, same slot positions).
  const today = todayIso();
  // ?? null keeps an old backend (field missing) on the previous blank look.
  const anchorVal: number | null = elo.anchor_points ?? null;
  const valueOf = (b: (typeof elo.buckets)[number]): number | null =>
    b.date_from > today ? null : b.rating_end ?? anchorVal;
  const drawn = elo.buckets
    .map(valueOf)
    .filter((v): v is number => v !== null);
  const base = Math.min(...drawn) - 20;
  const sign = elo.total_delta > 0 ? "+" : "";
  return (
    <div className="stat-block elo-block">
      <div className="elo-head">
        <h3>📈 ELO</h3>
        <span
          className={`elo-chip ${elo.total_delta >= 0 ? "elo-up" : "elo-down"}`}
          title="Net Δ in the visible range (ELO-counted matches)"
        >
          {sign}
          {elo.total_delta.toFixed(1)} · {elo.counted} matches
        </span>
        <span className="elo-endnote">
          {elo.rating_start !== null && elo.rating_start !== elo.rating_end
            ? `${elo.rating_start} → `
            : ""}
          period end <b>{elo.rating_end}</b>
        </span>
      </div>
      {drawn.length > 1 && (
        <LineChart
          points={elo.buckets.map((b) => {
            const v = valueOf(b);
            return {
              label: b.label,
              value: v === null ? null : v - base,
              display:
                b.rating_end === null
                  ? `${anchorVal} · before anchor`
                  : `${b.rating_end} · Δ ${b.delta > 0 ? "+" : ""}${b.delta.toFixed(1)}${
                      b.counted ? ` (${b.counted} matches)` : ""
                    }`,
              tip: b.date_from === b.date_to ? prettyDate(b.date_from) : b.label,
            };
          })}
          formatY={(v) => String(Math.round(v + base))}
          gutter={`${unitIsDay ? gutterPx : 46}px`}
        />
      )}
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
function CoachPackageCard({
  current,
  onStartNext,
  busy,
}: {
  current: CoachPackage;
  // Renew action: mark session size+1 as the new package's start.
  onStartNext: () => void;
  busy: boolean;
}) {
  return (
    <div className={`stat-card pkg-card pkg-${current.status}`}>
      <div className="stat-card-title">Coach package</div>
      <div className="stat-big">
        {current.used}
        <span className="stat-of">/{current.size}</span>
      </div>
      <div className="stat-sub">started {prettyDate(current.start_date)}</div>
      <div className="pkg-status">{pkgStatusText(current)}</div>
      {current.status === "over" && (
        <button className="btn primary" onClick={onStartNext} disabled={busy}>
          ★ Start new package from session {current.size + 1}
        </button>
      )}
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
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [buckets, setBuckets] = useState<BreakdownBucket[]>([]);
  const [elo, setElo] = useState<RatingBreakdown | null>(null);
  const [packages, setPackages] = useState<CoachPackage[]>([]);
  const [pkgBusy, setPkgBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Open drill-down: which card's matches to list, optionally W/L-filtered.
  const [drill, setDrill] = useState<{
    bucket: StatBucket;
    title: string;
    result: ResultFilter;
  } | null>(null);

  // Renew flow: the card's button flags session size+1 as the new package's
  // start; the response already carries the recomputed package list.
  const startNextPackage = async () => {
    setPkgBusy(true);
    try {
      const r = await trackerApi.startNextCoachPackage();
      setPackages(r.packages);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPkgBusy(false);
    }
  };

  const chartUnit: Unit | null = chartUnitFor(mode, "line", fromIso, rangeToIso);

  // Drops out-of-order responses (rapid Prev/Prev clicks): only the newest
  // in-flight load may write state. Same pattern as useLoad's seq counter.
  const seq = useRef(0);
  const load = useCallback(async () => {
    const mySeq = ++seq.current;
    if (fromIso > rangeToIso) {
      setError("'From' date is after 'To' date.");
      setStats(null);
      setBuckets([]);
      setElo(null);
      return;
    }
    try {
      setError(null);
      const [s, b, r] = await Promise.all([
        trackerApi.getStats(fromIso, rangeToIso),
        chartUnit
          ? trackerApi.getBreakdown(fromIso, rangeToIso, chartUnit)
          : Promise.resolve(null),
        // Day granularity even without a chart (single-day mode still shows
        // the "how much did today move me" header).
        trackerApi.ratingBreakdown(fromIso, rangeToIso, chartUnit ?? "day"),
      ]);
      if (mySeq !== seq.current) return; // stale response
      setStats(s);
      setBuckets(b ? b.buckets : []);
      setElo(r);
    } catch (e) {
      if (mySeq !== seq.current) return;
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

            {/* 1v2/2v1 are logged (rare formats, entered for the data) but
                not worth a daily card — their matches still count in "All
                matches" and can be filtered in Match Stats. */}
            {(
              [
                ["Singles", "singles", stats.singles],
                ["Doubles", "doubles", stats.doubles],
                ["All matches", "overall", stats.overall],
                ["🏓 vs Pips", "vs_pips", stats.vs_pips],
              ] as [string, StatBucket, MatchStats][]
            ).map(([title, bucket, s]) => (
              <MatchCard
                key={bucket}
                title={title}
                s={s}
                onOpen={(result) => setDrill({ bucket, title, result })}
              />
            ))}

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

          {drill && (
            <StatMatchesModal
              bucket={drill.bucket}
              title={drill.title}
              rangeLabel={label}
              fromIso={fromIso}
              toIso={rangeToIso}
              initialResult={drill.result}
              onClose={() => setDrill(null)}
            />
          )}
        </>
      )}
    </section>
  );
}
