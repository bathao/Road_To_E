// Status strip under the toolbar (above the grid): up to MAX_SHOWN upcoming
// tournaments within STRIP_HORIZON days, one line each, nearest first; a
// "+N giải nữa" button expands to every upcoming tournament (any horizon).
// Hidden entirely when nothing is coming up — it must cost zero space on
// ordinary days. Clicking anywhere else scrolls to the management section.
import { useState } from "react";
import type { Tournament } from "../../types";
import { countdownText, daysUntil, entryLabel, isPast } from "./helpers";

const STRIP_HORIZON = 45; // days
const MAX_SHOWN = 3;

export default function TournamentStrip({
  tournaments,
  onManage,
}: {
  tournaments: Tournament[];
  onManage: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const upcoming = tournaments.filter((t) => !isPast(t));
  const near = upcoming
    .filter((t) => daysUntil(t) <= STRIP_HORIZON)
    .slice(0, MAX_SHOWN);
  if (near.length === 0) return null;
  const shown = expanded ? upcoming : near;
  const hidden = upcoming.length - shown.length;

  return (
    <div
      className={`tour-strip${daysUntil(shown[0]) <= 7 ? " urgent" : ""}`}
      onClick={onManage}
      title="Bấm để xem / sửa danh sách giải (cuối trang)"
    >
      <div className="tour-strip-rows">
        {shown.map((t, i) => (
          <div key={t.id} className="tour-strip-row">
            <span className="tour-strip-name">🏆 {t.name}</span>
            <span
              className={`tour-strip-count${daysUntil(t) <= 7 ? " urgent" : ""}`}
            >
              {countdownText(t)}
            </span>
            {t.level_limit && (
              <span className="tour-chip tour-chip-limit">
                Trình: {t.level_limit}
              </span>
            )}
            {t.entries.map((e) => (
              <span key={e.id} className="tour-chip">
                {entryLabel(e)}
              </span>
            ))}
            {i === shown.length - 1 && (hidden > 0 || expanded) && (
              <button
                className="tour-strip-more"
                // The strip itself scrolls to the section — don't let the
                // expand/collapse click bubble into that.
                onClick={(e) => {
                  e.stopPropagation();
                  setExpanded((v) => !v);
                }}
              >
                {expanded ? "Show less" : `+${hidden} more`}
              </button>
            )}
          </div>
        ))}
      </div>
      <span className="tour-strip-manage">Quản lý ↓</span>
    </div>
  );
}
