import { useMemo, useState } from "react";
import { useLoad } from "../../shared/useApi";
import PeriodControl from "../../shared/ui/PeriodControl";
import type { Bar } from "../../shared/ui/LineChart";
import LineChart from "../../shared/ui/LineChart";
import LevelBars from "./components/LevelBars";
import { startOfMonth, toIso } from "../../shared/dates";
import type { Mode } from "../../shared/period";
import { chartUnitFor, resolveRange, stepAnchor } from "../../shared/period";
import { levelShort } from "../../shared/levels";
import { pct } from "../../shared/format";
import { matchStatsApi } from "./api";
import MatchLines from "./components/MatchLines";
import EloSection from "./components/EloSection";
import type {
  CategoryFilter,
  DisciplineFilter,
  MatchStatsResponse,
  PlayerLevel,
  RatingBreakdown,
} from "./types";

export default function MatchStats() {
  // Stats benefit from a wide default window → open on the current year.
  const [mode, setMode] = useState<Mode>("year");
  const [anchor, setAnchor] = useState<Date>(() => new Date());
  const [customFrom, setCustomFrom] = useState<string>(() =>
    toIso(startOfMonth(new Date()))
  );
  const [customTo, setCustomTo] = useState<string>(() => toIso(new Date()));
  const [discipline, setDiscipline] = useState<DisciplineFilter>("all");
  const [category, setCategory] = useState<CategoryFilter>("all");

  const [selOpp, setSelOpp] = useState<number | "">(""); // head-to-head dropdown

  const period = { mode, anchor, customFrom, customTo };
  const range = useMemo(
    () => resolveRange(period),
    [mode, anchor, customFrom, customTo]
  );
  const unit = chartUnitFor(mode, "line", range.fromIso, range.toIso) ?? "day";

  const { data, error, loading } = useLoad<MatchStatsResponse>(() => {
    setSelOpp(""); // reset the head-to-head pick when the dataset changes
    return matchStatsApi.get(range.fromIso, range.toIso, discipline, category, unit);
  }, [range.fromIso, range.toIso, discipline, category, unit]);

  // ELO over time — global, so it deliberately ignores the two filters.
  const { data: elo } = useLoad<RatingBreakdown>(
    () => matchStatsApi.ratingBreakdown(range.fromIso, range.toIso, unit),
    [range.fromIso, range.toIso, unit]
  );

  const o = data?.overall;
  const hasMatches = !!o && o.total > 0;

  // Trend: only periods that actually had matches, so the line never crashes
  // to 0% for months with no games.
  const trendPoints: Bar[] = (data?.trend ?? [])
    .filter((b) => b.matches > 0)
    .map((b) => ({
      label: b.label,
      value: b.win_rate === null ? 0 : Math.round(b.win_rate * 100),
      display: pct(b.win_rate),
      tip: `${b.label}: ${b.wins}-${b.losses} · ${b.matches} trận`,
    }));

  return (
    <div className="stats">
      <PeriodControl
        mode={mode}
        label={range.label}
        customFrom={customFrom}
        customTo={customTo}
        onMode={setMode}
        onStep={(dir) => setAnchor((a) => stepAnchor(mode, a, dir))}
        onToday={() => setAnchor(new Date())}
        onCustomFrom={setCustomFrom}
        onCustomTo={setCustomTo}
      />

      <div className="stats-filters">
        <div className="seg">
          {(
            [
              ["all", "Tất cả"],
              ["singles", "Singles"],
              ["doubles", "Doubles"],
              ["one_v_two", "1v2"],
              ["two_v_one", "2v1"],
            ] as [DisciplineFilter, string][]
          ).map(([k, lbl]) => (
            <button
              key={k}
              className={`seg-btn${discipline === k ? " active" : ""}`}
              onClick={() => setDiscipline(k)}
            >
              {lbl}
            </button>
          ))}
        </div>
        <div className="seg">
          {(
            [
              ["all", "Mọi loại"],
              ["practice", "Practice"],
              ["official", "Official"],
              ["tournament", "Tournament"],
            ] as [CategoryFilter, string][]
          ).map(([k, lbl]) => (
            <button
              key={k}
              className={`seg-btn${category === k ? " active" : ""}`}
              onClick={() => setCategory(k)}
            >
              {lbl}
            </button>
          ))}
        </div>
      </div>

      {error && <div className="pb-error">{error}</div>}

      {loading && !data ? (
        <div className="loading">Loading…</div>
      ) : !hasMatches ? (
        <p className="stats-empty">
          Chưa có trận nào (có tên đối thủ) trong khoảng này. Tab thống kê chỉ tính
          các trận đã chọn đối thủ — hãy ghi vài trận ở Daily Tracker, hoặc đổi
          khoảng thời gian.
        </p>
      ) : (
        <>
          {/* KPI cards */}
          <div className="stats-kpis">
            <div className="kpi">
              <span className="kpi-value">{o!.total}</span>
              <span className="kpi-label">Trận</span>
            </div>
            <div className="kpi">
              <span className="kpi-value">
                {o!.wins}-{o!.losses}
                {o!.ties ? `-${o!.ties}` : ""}
              </span>
              <span className="kpi-label">W-L{o!.ties ? "-T" : ""}</span>
            </div>
            <div className="kpi">
              <span className="kpi-value accent">{pct(o!.win_rate)}</span>
              <span className="kpi-label">Win rate</span>
            </div>
          </div>

          {/* Three analytic blocks side-by-side (≈1/3 each on wide screens). */}
          <div className="stats-cols">
          {/* Win rate by opponent level */}
          <section className="stats-card">
            <h3>Win rate theo trình đối thủ</h3>
            <LevelBars levels={data!.by_level} />
          </section>

          {/* Trend over time */}
          <section className="stats-card">
            <h3>
              Xu hướng win rate (
              {data!.unit === "month"
                ? "theo tháng"
                : data!.unit === "week"
                ? "theo tuần"
                : "theo ngày"}
              )
            </h3>
            {trendPoints.length > 1 ? (
              <LineChart points={trendPoints} formatY={(v) => `${Math.round(v)}%`} />
            ) : (
              <p className="stats-muted">
                Chưa đủ dữ liệu để vẽ xu hướng (cần ≥2 kỳ có trận).
              </p>
            )}
          </section>

          {/* Head-to-head — pick one opponent from the dropdown */}
          <section className="stats-card">
            <h3>Đối đầu (chọn đối thủ)</h3>
            <select
              className="pb-select stats-opp-select"
              value={selOpp}
              onChange={(e) => setSelOpp(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">— Chọn đối thủ ({data!.opponents.length}) —</option>
              {data!.opponents.map((op) => (
                <option key={op.id} value={op.id}>
                  {op.name} · {levelShort(op.level)} · {op.played} trận
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
                      Chưa có trận nào với đối thủ này trong khoảng đang chọn.
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
                    {played} trận · {w}-{l}
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
                      const fmtLabel =
                        d.discipline === "one_v_two"
                          ? "1v2"
                          : d.discipline === "two_v_one"
                          ? "2v1"
                          : "Đôi";
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
                                {fmtLabel} · tôi
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
          </div>
        </>
      )}

      {/* ELO over time — shown even when the filtered match list is empty
          (the rating is global and does not follow the filters). */}
      {elo && <EloSection elo={elo} unit={unit} />}
    </div>
  );
}
