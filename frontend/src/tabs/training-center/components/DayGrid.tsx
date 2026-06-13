import { DAY_ICON } from "../constants";
import type { DayTile } from "../types";

interface Props {
  tiles: DayTile[];
  /** day_index currently shown in the detail panel (highlighted). */
  activeDay: number | null;
  /** Open a tile's session detail (only unlocked / done tiles are clickable). */
  onPick: (tile: DayTile) => void;
}

/** BetterMe-style grid of "Day" tiles, unlocked sequentially. */
export default function DayGrid({ tiles, activeDay, onPick }: Props) {
  return (
    <div className="tc-grid">
      {tiles.map((tile) => {
        const locked = tile.status === "locked";
        const done = tile.status === "done";
        const cls = [
          "tc-tile",
          `tc-tile-${tile.status}`,
          tile.day_index === activeDay ? "tc-tile-active" : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <button
            key={tile.day_index}
            className={cls}
            disabled={locked}
            onClick={() => !locked && onPick(tile)}
            title={tile.focus_vi}
          >
            <span className="tc-tile-icon">{DAY_ICON[tile.day_type]}</span>
            <span className="tc-tile-day">Day {tile.day_index}</span>
            <span className="tc-tile-badge">
              {locked ? "🔒" : done ? "✅" : "🔓"}
            </span>
          </button>
        );
      })}
    </div>
  );
}
