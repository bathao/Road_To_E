import SearchPicker from "../../../shared/ui/SearchPicker";
import type { Opponent } from "../types";

// Type-to-search opponent picker for the Tactics tab (replaced the plain
// <select> on 2026-10-10 — 99 opponents sorted by matches played meant a
// player met once sat at the very bottom). The combo itself is the shared
// SearchPicker since 2026-10-15; this wrapper only knows how to describe a
// singles opponent. Nobody can be ADDED here — only people already played
// in singles have a tactics page (the backend builds the list).
function describe(o: Opponent): string {
  const n = o.matches_vs;
  return `${n} ${n === 1 ? "match" : "matches"} (${o.wins}W–${o.losses}L)`;
}

export default function OpponentPicker({
  opponents,
  selected,
  onPick,
}: {
  opponents: Opponent[];
  selected: Opponent | null;
  onPick: (id: number | null) => void;
}) {
  return (
    <SearchPicker
      className="tac-pick"
      items={opponents}
      selected={selected}
      onPick={onPick}
      describe={(o, where) =>
        describe(o) + (where === "list" && o.plays_pips ? " · pips" : "")
      }
      pillExtra={(o) =>
        o.plays_pips ? (
          <span className="pips-chip" title="Opponent plays pips">
            🏓 Pips
          </span>
        ) : null
      }
      placeholder="Search an opponent…"
      emptyText={(q) => `No singles opponent matches “${q}”.`}
    />
  );
}
