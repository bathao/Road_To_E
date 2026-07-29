// A summary card for one discipline (or overall). The whole card opens the
// drill-down list; clicking the W / L count opens it pre-filtered to just
// those matches.
import type { MatchStats } from "../types";
import { pct } from "../../../shared/format";
import type { ResultFilter } from "./StatMatchesModal";

export default function MatchCard({
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
