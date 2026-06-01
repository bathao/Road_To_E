import { prettyDate } from "../dates";

// Week navigation bar: ◀ / This week / ▶ plus the current week's date range.
export default function WeekNav({
  startIso,
  endIso,
  onPrev,
  onNext,
  onThisWeek,
}: {
  startIso: string;
  endIso: string;
  onPrev: () => void;
  onNext: () => void;
  onThisWeek: () => void;
}) {
  return (
    <div className="week-nav">
      <button className="btn" onClick={onPrev} aria-label="Previous week">
        ◀
      </button>
      <button className="btn" onClick={onThisWeek}>
        This week
      </button>
      <button className="btn" onClick={onNext} aria-label="Next week">
        ▶
      </button>
      <span className="week-range">
        {prettyDate(startIso)} — {prettyDate(endIso)}
      </span>
    </div>
  );
}
