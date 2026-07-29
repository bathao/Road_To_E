// Competitive snapshot over the selected range: overall win rate + one card
// per relative opponent level.
import { LEVELS } from "../../../shared/levels";
import { pct } from "../../../shared/format";
import type { MatchStatsLite } from "../types";

export default function CompetitiveCard({ match }: { match: MatchStatsLite | null }) {
  const byLevel = new Map((match?.by_level ?? []).map((r) => [r.level, r.stats]));
  return (
    <section className="va-card">
      <h3>🏆 Competitive record</h3>
      {match && match.overall.total > 0 ? (
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-card-title">Win rate (overall)</div>
            <div className="stat-big">{pct(match.overall.win_rate)}</div>
            <div className="stat-line muted">
              <span>{match.overall.total} matches</span>
              <span>
                <span className="win">{match.overall.wins}W</span> ·{" "}
                <span className="loss">{match.overall.losses}L</span>
              </span>
            </div>
          </div>
          {LEVELS.map((lv) => {
            const st = byLevel.get(lv.key);
            return (
              <div key={lv.key} className="stat-card">
                <div className="stat-card-title">Opponents {lv.label}</div>
                <div className="stat-big">{pct(st?.win_rate ?? null)}</div>
                <div className="stat-line muted">
                  <span>{st?.total ?? 0} matches</span>
                  <span>
                    <span className="win">{st?.wins ?? 0}W</span> ·{" "}
                    <span className="loss">{st?.losses ?? 0}L</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="va-muted">No matches with a named opponent in this range.</p>
      )}
    </section>
  );
}
