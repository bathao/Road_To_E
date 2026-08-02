import { useEffect, useMemo, useState } from "react";
import { useLoad } from "../../shared/useApi";
import { dmyDate, startOfMonth, toIso } from "../../shared/dates";
import {
  DISCIPLINES,
  DISCIPLINE_LABEL,
  DISCIPLINE_SHORT,
} from "../../shared/disciplines";
import { ROUND_SHORT } from "../../shared/matches";
import type { TournamentRound } from "../../shared/matches";
import { chartUnitFor } from "../../shared/period";
import RangePicker, { resolvePreset } from "./components/RangePicker";
import type { RangePreset } from "./components/RangePicker";
import { levelShort } from "../../shared/levels";
import { pct } from "../../shared/format";
import Seg from "../../shared/ui/Seg";
import { trainingApi } from "../training-center/api";
import { matchStatsApi } from "./api";
import MatchLines from "./components/MatchLines";
import { EloCurveCard, EloTableCard } from "./components/EloSection";
import GeneralInfoCard from "./components/GeneralInfoCard";
import TournamentRecord from "./components/TournamentRecord";
import TrainingCenterCard from "./components/TrainingCenterCard";
import TrainingDisciplineCard from "./components/TrainingDisciplineCard";
import type {
  CategoryFilter,
  DisciplineFilter,
  MatchStatsResponse,
  PlayerLevel,
  RatingBreakdown,
  TrackerStats,
} from "./types";

export default function MatchStats() {
  // YouTube-Studio-style range picker (user request 2026-08-02): rolling
  // windows ending today, whole years, recent months, custom. Default is
  // the rolling "Last 28 days" (replaced the calendar current-month default).
  const [preset, setPreset] = useState<RangePreset>("last28");
  const [customFrom, setCustomFrom] = useState<string>(() =>
    toIso(startOfMonth(new Date()))
  );
  const [customTo, setCustomTo] = useState<string>(() => toIso(new Date()));
  const [discipline, setDiscipline] = useState<DisciplineFilter>("all");
  const [category, setCategory] = useState<CategoryFilter>("all");

  const [selOpp, setSelOpp] = useState<number | "">(""); // head-to-head dropdown
  // Which KPI drill-down is open below the KPI row: the match list (Matches /
  // W-L / Win rate tiles), the same list filtered to pips opponents, or the
  // new-opponents table. One panel at a time.
  const [panel, setPanel] = useState<false | "matches" | "pips" | "new">(false);
  const [resFilter, setResFilter] = useState<"all" | "W" | "L">("all");

  // Earliest tracked data: opens the Lifetime range + bounds the picker's
  // year/month lists.
  const { data: firstDate } = useLoad<{ date: string | null }>(
    () => matchStatsApi.firstDate(),
    []
  );
  const first = firstDate?.date ?? null;
  const range = useMemo(
    () => resolvePreset(preset, customFrom, customTo, first),
    [preset, customFrom, customTo, first]
  );
  // Chart granularity follows the span (rolling windows have no mode).
  const unit =
    chartUnitFor("custom", "line", range.fromIso, range.toIso) ?? "day";

  const { data, error, loading } = useLoad<MatchStatsResponse>(
    () => matchStatsApi.get(range.fromIso, range.toIso, discipline, category, unit),
    [range.fromIso, range.toIso, discipline, category, unit]
  );

  // Reset the head-to-head pick when the dataset changes (an effect, not a
  // side effect inside the loader — setState in a fetcher body is fragile).
  useEffect(() => {
    setSelOpp("");
    setPanel(false);
    setResFilter("all");
  }, [range.fromIso, range.toIso, discipline, category, unit]);

  // ELO over time — global, so it deliberately ignores the two filters.
  const { data: elo } = useLoad<RatingBreakdown>(
    () => matchStatsApi.ratingBreakdown(range.fromIso, range.toIso, unit),
    [range.fromIso, range.toIso, unit]
  );

  // Bottom section (merged from the retired Profile tab 2026-07-30):
  // training discipline follows the range picker; the Training Center
  // report is rangeless (always the latest).
  const { data: training } = useLoad<TrackerStats>(
    () => matchStatsApi.trainingStats(range.fromIso, range.toIso),
    [range.fromIso, range.toIso]
  );
  const { data: trainingReport } = useLoad(() => trainingApi.getReport(), []);

  // Drill-down rows for the "New opponents" KPI — assembled from the h2h
  // records already in the response (singles + any team-style matchup they
  // appear in), so no extra endpoint. First met = earliest match in range,
  // which for a NEW opponent is their first match ever.
  const newOpps = useMemo(() => {
    if (!data) return [];
    return data.opponents
      .filter((op) => op.is_new)
      .map((op) => {
        const singles = data.singles_h2h.find((r) => r.opponent_id === op.id);
        const doubles = data.doubles_h2h.filter(
          (d) => d.opp1_id === op.id || d.opp2_id === op.id
        );
        const recs = [...(singles ? [singles] : []), ...doubles];
        const dates = recs.flatMap((r) => r.matches.map((m) => m.date));
        return {
          ...op,
          wins: recs.reduce((s, r) => s + r.wins, 0),
          losses: recs.reduce((s, r) => s + r.losses, 0),
          firstDate: dates.length
            ? dates.reduce((a, b) => (b < a ? b : a))
            : null,
        };
      })
      .sort((a, b) => (b.firstDate ?? "").localeCompare(a.firstDate ?? ""));
  }, [data]);

  // Every match in range, flattened from the same h2h records the KPI
  // numbers are built from — the drill-down list and the tiles can never
  // disagree. Newest first.
  const allMatches = useMemo(() => {
    if (!data) return [];
    interface Row {
      date: string;
      disc: string;
      my: number;
      opp: number;
      result: "W" | "L" | "T";
      vs: string;
      withPartner: string | null;
      hdc: string | null;
      event: string | null;
      round: string | null;
      oppIds: number[];
    }
    const hdcText = (handicap: number, pattern?: string | null) =>
      handicap === 0
        ? null
        : `${handicap > 0 ? "give" : "receive"} ${pattern ?? Math.abs(handicap)}`;
    const rows: Row[] = [];
    for (const r of data.singles_h2h) {
      for (const m of r.matches) {
        rows.push({
          date: m.date,
          disc: m.discipline,
          my: m.my_sets,
          opp: m.opp_sets,
          result: m.result,
          vs: r.name,
          withPartner: null,
          hdc: hdcText(m.handicap, m.handicap_pattern),
          event: m.event_name,
          round: m.round ?? null,
          oppIds: [r.opponent_id],
        });
      }
    }
    for (const r of data.doubles_h2h) {
      for (const m of r.matches) {
        rows.push({
          date: m.date,
          disc: m.discipline,
          my: m.my_sets,
          opp: m.opp_sets,
          result: m.result,
          vs: [r.opp1_name, r.opp2_name].filter(Boolean).join(" & "),
          withPartner: r.partner_name,
          hdc: hdcText(m.handicap, m.handicap_pattern),
          event: m.event_name,
          round: m.round ?? null,
          oppIds: [r.opp1_id, ...(r.opp2_id != null ? [r.opp2_id] : [])],
        });
      }
    }
    return rows.sort((a, b) => b.date.localeCompare(a.date));
  }, [data]);

  // Live pips flags (OpponentBrief) → which rows count as "vs pips".
  const pipsIds = useMemo(
    () =>
      new Set(
        (data?.opponents ?? []).filter((op) => op.plays_pips).map((op) => op.id)
      ),
    [data]
  );

  const shownMatches = useMemo(() => {
    let rows = allMatches;
    if (panel === "pips") {
      rows = rows.filter((m) => m.oppIds.some((id) => pipsIds.has(id)));
    }
    if (resFilter !== "all") rows = rows.filter((m) => m.result === resFilter);
    return rows;
  }, [allMatches, panel, pipsIds, resFilter]);

  const o = data?.overall;
  const hasMatches = !!o && o.total > 0;
  // The two card rows render when either side has content: the ELO cards are
  // global (they ignore the filters), the rest needs matches in range.
  const showCards = hasMatches || !!elo;

  return (
    <div className="stats">
      {/* 1) General info — rangeless header (avatar, current ELO). */}
      <GeneralInfoCard />

      <RangePicker
        preset={preset}
        customFrom={customFrom}
        customTo={customTo}
        firstDate={first}
        onPreset={setPreset}
        onCustomFrom={setCustomFrom}
        onCustomTo={setCustomTo}
      />

      <div className="stats-filters">
        <Seg<DisciplineFilter>
          options={[["all", "All"], ...DISCIPLINES] as [DisciplineFilter, string][]}
          value={discipline}
          onChange={setDiscipline}
        />
        <Seg<CategoryFilter>
          options={[
            ["all", "All types"],
            ["practice", "Practice"],
            ["official", "Official"],
            ["tournament", "Tournament"],
          ]}
          value={category}
          onChange={setCategory}
        />
      </div>

      {error && <div className="pb-error">{error}</div>}

      {loading && !data ? (
        <div className="loading">Loading…</div>
      ) : !hasMatches ? (
        <p className="stats-empty">
          No matches (with a named opponent) in this range. The stats tab only
          counts matches with an opponent selected — log a few matches in the
          Daily Tracker, or change the time range.
        </p>
      ) : (
        <div className="stats-kpis">
          {/* Matches / W-L / Win rate are three views of the same set, so
              all three open the same match-list drill-down below. */}
          <div
            className="kpi kpi-btn"
            title="All matches in this range (with the filters above). Click to list them."
            onClick={() => setPanel((p) => (p === "matches" ? false : "matches"))}
          >
            <span className="kpi-value">{o!.total}</span>
            <span className="kpi-label">
              Matches{panel === "matches" ? " ▾" : " ▸"}
            </span>
          </div>
          <div
            className="kpi kpi-btn"
            title="All matches in this range (with the filters above). Click to list them."
            onClick={() => setPanel((p) => (p === "matches" ? false : "matches"))}
          >
            <span className="kpi-value">
              {o!.wins}-{o!.losses}
              {o!.ties ? `-${o!.ties}` : ""}
            </span>
            <span className="kpi-label">
              W-L{o!.ties ? "-T" : ""}
              {panel === "matches" ? " ▾" : " ▸"}
            </span>
          </div>
          <div
            className="kpi kpi-btn"
            title="All matches in this range (with the filters above). Click to list them."
            onClick={() => setPanel((p) => (p === "matches" ? false : "matches"))}
          >
            <span className="kpi-value accent">{pct(o!.win_rate)}</span>
            <span className="kpi-label">
              Win rate{panel === "matches" ? " ▾" : " ▸"}
            </span>
          </div>
          <div
            className={`kpi${data!.vs_pips.total > 0 ? " kpi-btn" : ""}`}
            title={
              data!.vs_pips.total > 0
                ? `Matches where an opponent plays pimpled rubber ("gai"): ${data!.vs_pips.wins}W–${data!.vs_pips.losses}L of ${data!.vs_pips.total}. Click to list them.`
                : "No matches against a pimpled-rubber opponent in this range"
            }
            onClick={() =>
              data!.vs_pips.total > 0 &&
              setPanel((p) => (p === "pips" ? false : "pips"))
            }
          >
            <span className="kpi-value accent">
              {pct(data!.vs_pips.win_rate)}
            </span>
            <span className="kpi-label">
              Win rate vs pips 🏓
              {data!.vs_pips.total > 0 &&
                ` (${data!.vs_pips.wins}-${data!.vs_pips.losses})`}
              {data!.vs_pips.total > 0 && (panel === "pips" ? " ▾" : " ▸")}
            </span>
          </div>
          <div
            className={`kpi${data!.new_opponents > 0 ? " kpi-btn" : ""}`}
            title="Opponents who played a SINGLES match vs you in this range and whom you had never faced before it (any earlier match counts as faced; met only in doubles/team doesn't count). Click to see who."
            onClick={() =>
              data!.new_opponents > 0 &&
              setPanel((p) => (p === "new" ? false : "new"))
            }
          >
            <span className="kpi-value">{data!.new_opponents}</span>
            <span className="kpi-label">
              New opponents (singles)
              {data!.new_opponents > 0 && (panel === "new" ? " ▾" : " ▸")}
            </span>
          </div>
        </div>
      )}

      {/* Match-list drill-down (Matches / W-L / Win rate / vs-pips tiles) —
          same area and presentation as the new-opponents table below. */}
      {hasMatches && (panel === "matches" || panel === "pips") && (
        <section className="stats-card newopp-card">
          <h3>
            {panel === "pips"
              ? "🏓 Matches vs pips in this range"
              : "📋 Matches in this range"}
          </h3>
          <div className="stats-filters">
            <Seg<"all" | "W" | "L">
              options={[
                ["all", "All"],
                ["W", "Wins"],
                ["L", "Losses"],
              ]}
              value={resFilter}
              onChange={setResFilter}
            />
          </div>
          <table className="newopp-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Match</th>
                <th>Score</th>
                <th>Event</th>
              </tr>
            </thead>
            <tbody>
              {shownMatches.map((m, i) => (
                <tr key={`${m.date}-${i}`}>
                  <td>{dmyDate(m.date)}</td>
                  <td>
                    {DISCIPLINE_SHORT[m.disc as keyof typeof DISCIPLINE_SHORT]}{" "}
                    · vs {m.vs}
                    {m.withPartner ? ` (with ${m.withPartner})` : ""}
                    {m.hdc && <span className="newopp-pts"> · {m.hdc}</span>}
                  </td>
                  <td>
                    <span
                      className={`elo-td-res${
                        m.result === "W" ? " win" : m.result === "L" ? " loss" : ""
                      }`}
                    >
                      {m.my}-{m.opp}
                    </span>
                  </td>
                  <td>
                    {[
                      m.event,
                      m.round
                        ? ROUND_SHORT[m.round as TournamentRound]
                        : null,
                    ]
                      .filter(Boolean)
                      .join(" · ") || "—"}
                  </td>
                </tr>
              ))}
              {shownMatches.length === 0 && (
                <tr>
                  <td colSpan={4}>No matches.</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
      )}

      {/* "New opponents" drill-down: who they are, when first met, and the
          record so far — click a row to open their full head-to-head below. */}
      {hasMatches && panel === "new" && newOpps.length > 0 && (
        <section className="stats-card newopp-card">
          <h3>🆕 New opponents (singles) in this range</h3>
          <table className="newopp-table">
            <thead>
              <tr>
                <th>Opponent</th>
                <th>First met</th>
                <th>Matches</th>
                <th>W-L</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {newOpps.map((op) => (
                <tr key={op.id}>
                  <td>
                    {op.name}
                    {op.points != null && (
                      <span className="newopp-pts"> · {op.points}</span>
                    )}
                  </td>
                  <td>{op.firstDate ? dmyDate(op.firstDate) : "—"}</td>
                  <td>{op.played}</td>
                  <td>
                    {op.wins}-{op.losses}
                  </td>
                  <td>
                    <button
                      className="btn newopp-h2h"
                      onClick={() => setSelOpp(op.id)}
                    >
                      Head-to-head ↓
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {/* ELO curve row. (The "Results & form" W/L-bars chart was removed
          2026-08-01 on user request — ELO already tells the story; the
          "win rate by opponent level" bars went the same way 2026-07-29.) */}
      {showCards && elo && (
        <div className="stats-cols">
          {/* The ELO cards render even when the filtered match list is empty
              — the rating is global and does not follow the filters. */}
          <EloCurveCard elo={elo} unit={unit} />
        </div>
      )}

      {/* Lookup row: the per-match ELO table + head-to-head detail. */}
      {showCards && (
        <div className="stats-cols">
          {elo && <EloTableCard elo={elo} />}
          {hasMatches && (
          <section className="stats-card">
            <h3>Head-to-head (pick an opponent)</h3>
            <select
              className="pb-select stats-opp-select"
              value={selOpp}
              onChange={(e) => setSelOpp(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">— Pick an opponent ({data!.opponents.length}) —</option>
              {data!.opponents.map((op) => (
                <option key={op.id} value={op.id}>
                  {op.name} · {levelShort(op.level)} · {op.played} matches
                  {op.is_new ? " · NEW" : ""}
                </option>
              ))}
            </select>

            {selOpp !== "" &&
              (() => {
                const singlesRec = data!.singles_h2h.find(
                  (o) => o.opponent_id === selOpp
                );
                const doublesRecs = data!.doubles_h2h.filter(
                  (d) => d.opp1_id === selOpp || d.opp2_id === selOpp
                );
                if (!singlesRec && doublesRecs.length === 0) {
                  return (
                    <p className="stats-empty">
                      No matches with this opponent in the selected range.
                    </p>
                  );
                }
                const summary = (
                  w: number,
                  l: number,
                  t: number,
                  played: number,
                  wr: number | null
                ) => (
                  <span className="h2h-summary">
                    {played} matches · {w}-{l}
                    {t ? `-${t}` : ""} · <b>{pct(wr)}</b>
                  </span>
                );
                return (
                  <div className="stats-h2h-detail">
                    {singlesRec && (
                      <div className="h2h-group">
                        <div className="h2h-head">
                          <h4>Singles</h4>
                          {summary(
                            singlesRec.wins,
                            singlesRec.losses,
                            singlesRec.ties,
                            singlesRec.played,
                            singlesRec.win_rate
                          )}
                        </div>
                        <MatchLines rows={singlesRec.matches} />
                      </div>
                    )}
                    {doublesRecs.map((d) => {
                      const fmtLabel = DISCIPLINE_LABEL[d.discipline];
                      const pairLabel = (lvl: PlayerLevel | null, name: string | null) =>
                        name ? (
                          <span className="dbl-side" key={name}>
                            {name}{" "}
                            {lvl && (
                              <span className={`level-chip level-${lvl}`}>
                                {levelShort(lvl)}
                              </span>
                            )}
                          </span>
                        ) : null;
                      return (
                        <div className="h2h-group" key={d.key}>
                          <div className="h2h-head">
                            <h4 className="h2h-pair">
                              <span className="dbl-side">
                                {fmtLabel} · me
                                {d.partner_name ? ` + ${d.partner_name}` : ""}
                              </span>
                              <span className="dbl-vs">vs</span>
                              {pairLabel(d.opp1_level, d.opp1_name)}
                              {d.opp2_name ? (
                                <>
                                  {" & "}
                                  {pairLabel(d.opp2_level, d.opp2_name)}
                                </>
                              ) : null}
                            </h4>
                            {summary(d.wins, d.losses, d.ties, d.played, d.win_rate)}
                          </div>
                          <MatchLines rows={d.matches} />
                        </div>
                      );
                    })}
                  </div>
                );
              })()}
          </section>
          )}
        </div>
      )}

      {/* 3) Training row (merged from the retired Profile tab): discipline
          follows the range picker above; Training Center is rangeless. */}
      <div className="stats-cols">
        <TrainingDisciplineCard training={training ?? null} />
        <TrainingCenterCard report={trainingReport ?? null} />
      </div>

      {/* 4) Tournament record — read-only past-tournament history, rangeless
          (it deliberately ignores the range picker: a career record). */}
      <TournamentRecord />
    </div>
  );
}
