import { ROUND_SHORT } from "../../../shared/matches";
import type { TournamentRound } from "../../../shared/matches";
import type { MatchLine } from "../types";

// A clear, match-by-match list of set scores against one opponent (or pairing).
// Most recent first (the API reverses). Shows each match's score, result, and
// any handicap so the raw record is visible — not just an aggregate set±.
export default function MatchLines({ rows }: { rows: MatchLine[] }) {
  if (!rows.length) return null;
  return (
    <ol className="match-lines">
      {rows.map((m, i) => {
        // Non-uniform ratios show the per-set sequence ("2-0-2").
        const amount = m.handicap_pattern ?? String(Math.abs(m.handicap));
        const hc =
          m.handicap > 0
            ? `gave ${amount} handicap`
            : m.handicap < 0
            ? `got ${amount} handicap`
            : null;
        return (
          <li className="match-line" key={i}>
            <span className={`res res-${m.result}`}>{m.result}</span>
            <span className="ml-score">
              {m.my_sets}-{m.opp_sets}
            </span>
            <span className="ml-date">{m.date}</span>
            {hc && <span className="ml-hc">{hc}</span>}
            {m.round && ROUND_SHORT[m.round as TournamentRound] && (
              <span className="ml-event">
                {ROUND_SHORT[m.round as TournamentRound]}
              </span>
            )}
            {m.event_name && <span className="ml-event">{m.event_name}</span>}
          </li>
        );
      })}
    </ol>
  );
}
