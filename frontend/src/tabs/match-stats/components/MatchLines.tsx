import { dmyDate } from "../../../shared/dates";
import { hdcLabel, ROUND_SHORT } from "../../../shared/matches";
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
        const hc = hdcLabel(m.handicap, m.handicap_pattern);
        return (
          <li className="match-line" key={i}>
            <span className={`res res-${m.result}`}>{m.result}</span>
            <span className="ml-score">
              {m.my_sets}-{m.opp_sets}
            </span>
            <span className="ml-date">{dmyDate(m.date)}</span>
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
