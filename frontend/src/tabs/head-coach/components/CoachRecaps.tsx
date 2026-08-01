import { useEffect, useState } from "react";
import { headCoachApi } from "../api";
import { useLoad, useMutate } from "../../../shared/useApi";
import Seg from "../../../shared/ui/Seg";
import { prettyDate } from "../../../shared/dates";
import { fmtTime } from "../fmt";
import type { Recap, RecapPeriod, RecapPeriodStats, RecapsOut } from "../types";

const WINDOW_LABEL: Record<RecapPeriod, string> = {
  week: "Last 7 days",
  month: "Last 30 days",
};

function fmtEloDelta(d: number) {
  const v = Math.round(d * 10) / 10;
  return `${v > 0 ? "+" : ""}${v}`;
}

// One code-computed number, with the previous window's value underneath.
function Stat({
  label,
  value,
  prev,
  diff,
}: {
  label: string;
  value: string;
  prev?: string;
  // Signed comparison vs the previous window (colors the arrow); undefined
  // when there is nothing meaningful to compare.
  diff?: number;
}) {
  return (
    <div className="hc-stat">
      <div className="hc-stat-label">{label}</div>
      <div className="hc-stat-value">{value}</div>
      {prev !== undefined && (
        <div className="hc-stat-prev">
          {diff !== undefined && diff !== 0 && (
            <span className={diff > 0 ? "hc-diff-up" : "hc-diff-down"}>
              {diff > 0 ? "▲" : "▼"}{" "}
            </span>
          )}
          prev: {prev}
        </div>
      )}
    </div>
  );
}

function matchesText(s: RecapPeriodStats) {
  const wr = s.win_rate != null ? ` · ${Math.round(s.win_rate * 100)}%` : "";
  return `${s.matches_played} (${s.matches_wins}W–${s.matches_losses}L${wr})`;
}

function StatsRow({ recap }: { recap: Recap }) {
  const cur = recap.stats?.current;
  if (!cur) return null;
  const prev = recap.stats?.previous ?? null;
  return (
    <div className="hc-recap-stats">
      <Stat
        label="Active days"
        value={String(cur.days_trained)}
        prev={prev ? String(prev.days_trained) : undefined}
        diff={prev ? cur.days_trained - prev.days_trained : undefined}
      />
      <Stat
        label="Purposeful minutes"
        value={`${cur.minutes_total}m`}
        prev={prev ? `${prev.minutes_total}m` : undefined}
        diff={prev ? cur.minutes_total - prev.minutes_total : undefined}
      />
      <Stat
        label="Racket time"
        value={`${cur.racket_minutes_total}m`}
        prev={prev ? `${prev.racket_minutes_total}m` : undefined}
        diff={
          prev ? cur.racket_minutes_total - prev.racket_minutes_total : undefined
        }
      />
      <Stat
        label="Fitness sessions"
        value={String(cur.physical_sessions)}
        prev={prev ? String(prev.physical_sessions) : undefined}
        diff={prev ? cur.physical_sessions - prev.physical_sessions : undefined}
      />
      <Stat
        label="Matches"
        value={matchesText(cur)}
        prev={prev ? matchesText(prev) : undefined}
        diff={prev ? cur.matches_played - prev.matches_played : undefined}
      />
      <Stat
        label="New opponents"
        value={String(cur.new_opponents)}
        prev={prev ? String(prev.new_opponents) : undefined}
        diff={prev ? cur.new_opponents - prev.new_opponents : undefined}
      />
      <Stat
        label="ELO"
        value={
          cur.elo_end != null
            ? `${fmtEloDelta(cur.elo_delta)} → ${cur.elo_end}`
            : "pre-anchor"
        }
        prev={
          prev
            ? prev.elo_end != null
              ? `${fmtEloDelta(prev.elo_delta)} → ${prev.elo_end}`
              : "pre-anchor"
            : undefined
        }
        diff={prev && cur.elo_end != null ? cur.elo_delta : undefined}
      />
    </div>
  );
}

export default function CoachRecaps() {
  const [period, setPeriod] = useState<RecapPeriod>("week");

  const { data, error: loadError, loading, reload } = useLoad<RecapsOut>(
    () => headCoachApi.getRecaps(period),
    [period]
  );
  const { run, error: mutateError, clearError } = useMutate();

  const recap: Recap | null = data?.latest ?? null;
  const error = mutateError ?? loadError;
  const generating = recap?.status === "generating";

  // While generating, poll every 3s (same contract as the verdict).
  useEffect(() => {
    if (!generating) return;
    const timer = setInterval(() => reload(), 3000);
    return () => clearInterval(timer);
  }, [generating, reload]);

  // The button: recap the window ending RIGHT NOW (results up to today).
  const generate = async () => {
    clearError();
    const out = await run(() => headCoachApi.generateRecap(period));
    if (out !== undefined) reload();
  };

  const changePeriod = (p: RecapPeriod) => {
    setPeriod(p);
    clearError();
  };

  return (
    <div className="hc-recaps">
      <div className="hc-top">
        <div>
          <h2 className="hc-title">📅 Recaps</h2>
          <p className="hc-sub">
            The coach's review of your last 7 or 30 days, counted up to the
            moment you press the button. Nothing runs automatically.
          </p>
        </div>
        <div className="hc-recap-controls">
          <Seg<RecapPeriod>
            options={[
              ["week", "Last 7 days"],
              ["month", "Last 30 days"],
            ]}
            value={period}
            onChange={changePeriod}
          />
          <button className="btn primary" onClick={generate} disabled={generating}>
            {generating ? "⏳ Generating…" : recap ? "Generate again" : "Generate"}
          </button>
        </div>
      </div>

      {error && <div className="hc-error">⚠️ {error}</div>}

      {loading && !data && <div className="loading">Loading…</div>}

      {!loading && data && !recap && (
        <div className="hc-empty">
          No recap yet. Press <b>Generate</b> and the coach will review your
          last {period === "week" ? "7" : "30"} days.
        </div>
      )}

      {recap && (
        <div className="hc-recap">
          <div className="hc-recap-period">
            {WINDOW_LABEL[recap.period_type]} ·{" "}
            {prettyDate(recap.period_start)} – {prettyDate(recap.period_end)}
          </div>

          {recap.status === "generating" && (
            <div className="hc-note">
              The coach is reviewing your last{" "}
              {recap.period_type === "week" ? "7" : "30"} days (local model
              running in the background — you can switch tabs and come back)…
            </div>
          )}

          {recap.status === "error" && (
            <div className="hc-error">
              ⚠️ {recap.error_msg || "Recap generation failed."}{" "}
              <button className="btn" onClick={generate}>
                Retry
              </button>
            </div>
          )}

          {recap.status === "done" && (
            <>
              <StatsRow recap={recap} />
              {recap.stats && recap.stats.previous == null && (
                <div className="hc-recap-noprev">
                  No tracked data in the{" "}
                  {recap.period_type === "week" ? "7" : "30"} days before this
                  window — no comparison shown.
                </div>
              )}

              <section className="hc-overall">
                {recap.headline && <h3>{recap.headline}</h3>}
                <p>{recap.overall}</p>
              </section>

              {recap.went_well.length > 0 && (
                <section className="hc-section">
                  <h3>✅ What went well</h3>
                  <ul className="hc-recap-list">
                    {recap.went_well.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                </section>
              )}
              {recap.concerns.length > 0 && (
                <section className="hc-section hc-watch">
                  <h3>⚠️ Concerns</h3>
                  <ul className="hc-recap-list">
                    {recap.concerns.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                </section>
              )}
              {recap.focus_next.length > 0 && (
                <section className="hc-section">
                  <h3>
                    🎯 Focus for the next{" "}
                    {recap.period_type === "week" ? "7" : "30"} days
                  </h3>
                  <ul className="hc-recap-list">
                    {recap.focus_next.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                </section>
              )}

              <div className="hc-meta">
                Generated at {fmtTime(recap.created_at)} · model {recap.model}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
