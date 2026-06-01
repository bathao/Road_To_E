import { useCallback, useEffect, useMemo, useState } from "react";
import type { MatchStats, StatsResponse } from "../types";
import { trackerApi } from "../api";
import {
  addDays,
  addMonths,
  endOfMonth,
  monthLabel,
  mondayOf,
  prettyDate,
  startOfMonth,
  toIso,
} from "../dates";

type Mode = "day" | "week" | "month" | "custom";
const MODES: Mode[] = ["day", "week", "month", "custom"];
const MODE_LABEL: Record<Mode, string> = {
  day: "Day",
  week: "Week",
  month: "Month",
  custom: "Custom",
};

function fmtMinutes(min: number): string {
  if (!min) return "0m";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return [h ? `${h}h` : "", m ? `${m}m` : ""].filter(Boolean).join(" ");
}

function pct(rate: number | null): string {
  return rate === null ? "—" : `${Math.round(rate * 100)}%`;
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

// Analysis panel shown under the weekly grid. Has its own period selector
// (Day / Week / Month / Custom) independent of the grid's week.
export default function AnalysisPanel({
  reloadSignal,
}: {
  reloadSignal: number;
}) {
  const [mode, setMode] = useState<Mode>("week");
  const [anchor, setAnchor] = useState<Date>(() => new Date());
  const [customFrom, setCustomFrom] = useState<string>(() =>
    toIso(startOfMonth(new Date()))
  );
  const [customTo, setCustomTo] = useState<string>(() => toIso(new Date()));
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Resolve the active [from, to] range from the mode + anchor.
  const { fromIso, toIso: rangeToIso, label } = useMemo(() => {
    if (mode === "day") {
      const iso = toIso(anchor);
      return { fromIso: iso, toIso: iso, label: prettyDate(iso) };
    }
    if (mode === "week") {
      const start = mondayOf(anchor);
      const end = addDays(start, 6);
      return {
        fromIso: toIso(start),
        toIso: toIso(end),
        label: `${prettyDate(toIso(start))} — ${prettyDate(toIso(end))}`,
      };
    }
    if (mode === "month") {
      return {
        fromIso: toIso(startOfMonth(anchor)),
        toIso: toIso(endOfMonth(anchor)),
        label: monthLabel(anchor),
      };
    }
    return {
      fromIso: customFrom,
      toIso: customTo,
      label: `${prettyDate(customFrom)} — ${prettyDate(customTo)}`,
    };
  }, [mode, anchor, customFrom, customTo]);

  const load = useCallback(async () => {
    if (fromIso > rangeToIso) {
      setError("'From' date is after 'To' date.");
      setStats(null);
      return;
    }
    try {
      setError(null);
      setStats(await trackerApi.getStats(fromIso, rangeToIso));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [fromIso, rangeToIso]);

  useEffect(() => {
    void load();
    // reloadSignal changes when the grid data is mutated.
  }, [load, reloadSignal]);

  const step = (dir: number) => {
    if (mode === "day") setAnchor((a) => addDays(a, dir));
    else if (mode === "week") setAnchor((a) => addDays(a, dir * 7));
    else if (mode === "month") setAnchor((a) => addMonths(a, dir));
  };

  return (
    <section className="analysis">
      <div className="analysis-head">
        <h2>📊 Analysis</h2>
        <div className="seg">
          {MODES.map((m) => (
            <button
              key={m}
              className={`seg-btn${mode === m ? " active" : ""}`}
              onClick={() => setMode(m)}
            >
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>

        {mode === "custom" ? (
          <div className="custom-range">
            <input
              type="date"
              value={customFrom}
              onChange={(e) => setCustomFrom(e.target.value)}
            />
            <span>→</span>
            <input
              type="date"
              value={customTo}
              onChange={(e) => setCustomTo(e.target.value)}
            />
          </div>
        ) : (
          <div className="analysis-nav">
            <button className="btn" onClick={() => step(-1)} aria-label="Previous">
              ◀
            </button>
            <button className="btn" onClick={() => setAnchor(new Date())}>
              Today
            </button>
            <button className="btn" onClick={() => step(1)} aria-label="Next">
              ▶
            </button>
            <span className="analysis-range">{label}</span>
          </div>
        )}
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
          </div>

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

          {/* Per-day breakdown: which days had training / physical */}
          <div className="stat-block">
            <h3>By day</h3>
            <div className="day-table-wrap">
              <table className="day-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Trained</th>
                    <th>Physical</th>
                    <th>Matches</th>
                    <th>Time</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.days.map((d) => (
                    <tr key={d.date} className={d.trained ? "" : "rest-day"}>
                      <td className="day-cell">
                        {d.weekday} {prettyDate(d.date)}
                      </td>
                      <td>{d.trained ? "✅" : "—"}</td>
                      <td>
                        {d.physical ? `🟡 ${d.physical_count}` : "—"}
                      </td>
                      <td>{d.matches || "—"}</td>
                      <td>{d.minutes ? fmtMinutes(d.minutes) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
