import type { LevelInfo } from "../types";

interface Props {
  levels: LevelInfo[];
  selected: string;
  currentLevel: string;
  onSelect: (level: string) => void;
}

/** Chips to browse each level's grid; locked levels show their unlock hint. */
export default function LevelSwitcher({
  levels,
  selected,
  currentLevel,
  onSelect,
}: Props) {
  return (
    <div className="tc-levels">
      {levels.map((lv) => {
        const cls = [
          "tc-level-chip",
          lv.key === selected ? "active" : "",
          lv.unlocked ? "" : "locked",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <button
            key={lv.key}
            className={cls}
            disabled={!lv.unlocked}
            onClick={() => lv.unlocked && onSelect(lv.key)}
            title={
              lv.unlocked
                ? lv.goal_vi
                : "Hoàn thành cấp trước để mở khoá"
            }
          >
            <span className="tc-level-name">
              {lv.unlocked ? "" : "🔒 "}
              {lv.label_vi}
              {lv.key === currentLevel ? " ●" : ""}
            </span>
            <span className="tc-level-prog">
              {lv.completed}/{lv.total}
            </span>
          </button>
        );
      })}
    </div>
  );
}
