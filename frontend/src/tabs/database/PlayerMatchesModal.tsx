// Per-player drill-down behind the Database tab's match counts: every match
// involving the player (all-time), rendered with the same match lines as the
// Daily Tracker's Analysis drill-down. Opened from the "Vs me" / "With me"
// count cells, which preset the role filter.
import { useState } from "react";
import Modal from "../../shared/ui/Modal";
import { useLoad } from "../../shared/useApi";
import { resultOf } from "../../shared/types";
import type { Match } from "../daily-tracker/types";
import MatchRowList from "../daily-tracker/components/MatchRowList";
import { databaseApi } from "./api";
import type { PlayerDbRow } from "./types";

export type RoleFilter = "all" | "vs" | "with";
type ResultFilter = "all" | "W" | "L";

export default function PlayerMatchesModal({
  player,
  initialRole,
  onClose,
}: {
  player: PlayerDbRow;
  initialRole: RoleFilter;
  onClose: () => void;
}) {
  const [role, setRole] = useState<RoleFilter>(initialRole);
  const [result, setResult] = useState<ResultFilter>("all");
  const { data: matches, error, loading } = useLoad<Match[]>(
    () => databaseApi.playerMatches(player.id),
    [player.id]
  );

  const all = matches ?? [];
  const isWith = (m: Match) => m.partner_id === player.id;
  const byRole = all.filter((m) =>
    role === "all" ? true : role === "with" ? isWith(m) : !isWith(m)
  );
  const wins = byRole.filter((m) => resultOf(m) === "W");
  const losses = byRole.filter((m) => resultOf(m) === "L");
  const shown = result === "all" ? byRole : result === "W" ? wins : losses;

  // The role seg only earns its place when the player has both roles.
  const hasBothRoles = all.some(isWith) && all.some((m) => !isWith(m));

  return (
    <Modal title={`Matches · ${player.name}`} onClose={onClose}>
      <div className="pm-filters">
        {hasBothRoles && (
          <div className="seg smm-filter">
            {(
              [
                ["all", `All (${all.length})`],
                ["vs", `⚔️ Vs me (${all.filter((m) => !isWith(m)).length})`],
                ["with", `🤝 With me (${all.filter(isWith).length})`],
              ] as [RoleFilter, string][]
            ).map(([k, lbl]) => (
              <button
                key={k}
                className={`seg-btn${role === k ? " active" : ""}`}
                onClick={() => setRole(k)}
              >
                {lbl}
              </button>
            ))}
          </div>
        )}
        <div className="seg smm-filter">
          <button
            className={`seg-btn${result === "all" ? " active" : ""}`}
            onClick={() => setResult("all")}
          >
            All ({byRole.length})
          </button>
          <button
            className={`seg-btn${result === "W" ? " active" : ""}`}
            onClick={() => setResult("W")}
          >
            {wins.length}W
          </button>
          <button
            className={`seg-btn${result === "L" ? " active" : ""}`}
            onClick={() => setResult("L")}
          >
            {losses.length}L
          </button>
        </div>
      </div>

      {error && <div className="error-banner">⚠ {error}</div>}
      {loading && !matches && <p className="smm-empty">Loading…</p>}
      {matches && shown.length === 0 && (
        <p className="smm-empty">No matches here.</p>
      )}

      <MatchRowList matches={shown} />
    </Modal>
  );
}
