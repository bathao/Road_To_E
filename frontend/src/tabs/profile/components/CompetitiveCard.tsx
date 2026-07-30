// Competitive snapshot over the selected range. (The per-opponent-level
// cards were removed 2026-07-29 with Match Stats' level bars — the dynamic
// ELO already prices opponent strength.)
import { pct } from "../../../shared/format";
import type { MatchStatsLite } from "../types";

export default function CompetitiveCard({ match }: { match: MatchStatsLite | null }) {
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
        </div>
      ) : (
        <p className="va-muted">No matches with a named opponent in this range.</p>
      )}
    </section>
  );
}
