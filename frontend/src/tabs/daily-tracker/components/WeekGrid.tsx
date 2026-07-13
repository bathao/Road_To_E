import { useLayoutEffect, useRef } from "react";
import type { Category, WeekResponse } from "../types";
import { cellKey } from "../types";
import { dayHeader, monthGroups, todayIso } from "../../../shared/dates";

// The Excel-like weekly grid. Rows = categories, columns = 7 days.
// Clicking any cell opens the matching editor for that (category, date).
export default function WeekGrid({
  week,
  onCellClick,
  onViewPhysical,
  onLayout,
}: {
  week: WeekResponse;
  onCellClick: (category: Category, dateIso: string) => void;
  // Read-only view of a Training Center session mirrored into the Physical row.
  onViewPhysical: (dateIso: string) => void;
  // Reports the rendered width (px) of the leading Category column, so the
  // Analysis chart below can use it as a left gutter and line its day points
  // up under the grid's day columns. Re-fired on data change and resize.
  onLayout?: (gutterPx: number) => void;
}) {
  const today = todayIso();
  const wrapRef = useRef<HTMLDivElement>(null);
  const cornerRef = useRef<HTMLTableCellElement>(null);

  useLayoutEffect(() => {
    if (!onLayout) return;
    const measure = () => {
      const wrap = wrapRef.current;
      const corner = cornerRef.current;
      if (!wrap || !corner) return;
      // Day columns begin at the Category column's right edge, measured
      // relative to the grid wrapper (which shares its left edge with the
      // chart below, both being full-width siblings).
      onLayout(
        corner.getBoundingClientRect().right -
          wrap.getBoundingClientRect().left
      );
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (wrapRef.current) ro.observe(wrapRef.current);
    return () => ro.disconnect();
    // Re-measure whenever the column layout could change.
  }, [onLayout, week, week.days.length]);
  // Many columns (month / year / long custom range) → narrow, truncated cells
  // that reveal their full content on hover.
  const compact = week.days.length > 10;
  // When the range spans more than one month (Year, long custom), add a
  // grouping header row labelling each month.
  const groups = monthGroups(week.days);
  const showMonths = groups.length > 1;

  return (
    <div className="grid-wrap" ref={wrapRef}>
      <table className={compact ? "week-grid compact" : "week-grid"}>
        <thead>
          {showMonths && (
            <tr>
              <th className="corner" rowSpan={2} ref={cornerRef}>
                Category
              </th>
              {groups.map((g, i) => (
                <th key={i} className="month-head" colSpan={g.span}>
                  {g.label}
                </th>
              ))}
            </tr>
          )}
          <tr>
            {!showMonths && (
              <th className="corner" ref={cornerRef}>
                Category
              </th>
            )}
            {week.days.map((iso) => {
              const { weekday, dayNum } = dayHeader(iso);
              return (
                <th
                  key={iso}
                  className={iso === today ? "day-head today" : "day-head"}
                >
                  <div className="day-weekday">{weekday}</div>
                  <div className="day-num">{dayNum}</div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {week.categories.map((cat) => (
            <tr key={cat.id}>
              <th className={`row-head color-${cat.color_group}`}>
                {cat.label}
              </th>
              {week.days.map((iso) => {
                const cell = week.cells[cellKey(cat.id, iso)];
                const isToday = iso === today;
                const isRating = cat.type === "rating";
                // Auto-calculated row (Racket Time): shows text, never editable.
                const isComputed = cat.type === "computed";
                // Future days can't be logged yet — only today and the past.
                const isFuture = iso > today;
                // From the cutover forward the Physical row is a read-only
                // mirror of Training Center — log physical work over there.
                const isPhysicalMirror =
                  cat.key === "physical_training" &&
                  week.physical_cutover != null &&
                  iso >= week.physical_cutover;
                const editable =
                  !isRating && !isComputed && !isFuture && !isPhysicalMirror;
                const classes = ["cell", `type-${cat.type}`];
                if (isToday) classes.push("today");
                if (isRating || isComputed || isPhysicalMirror)
                  classes.push("readonly");
                if (isFuture) classes.push("future");
                // Fill the whole cell background with the day's color
                // (Overall row, and Physical Training when >=70% ticked).
                if (cell?.color) classes.push(`rating-${cell.color}`);
                // Hovering a cell reveals its full content — useful when narrow
                // columns truncate the text.
                const fullText =
                  cat.type === "note"
                    ? week.day_notes[iso] || ""
                    : cell?.display ?? "";
                // A mirrored Physical cell with data is clickable to VIEW the
                // Training Center session (read-only); empty mirror days aren't.
                const viewablePhysical = isPhysicalMirror && !!cell?.display;
                const title = isFuture
                  ? "Future date — you can only log today and past days"
                  : isRating
                    ? "Auto-generated from the day's data"
                    : isComputed
                      ? "Auto-computed: Coach + Partner training + 5 min per match set"
                      : viewablePhysical
                        ? "Bấm để xem buổi Training Center 💪"
                        : isPhysicalMirror
                          ? "Quản lý ở tab Training Center 💪"
                          : fullText
                            ? `${cat.label} · ${iso}\n${fullText}`
                            : undefined;
                const handleClick = editable
                  ? () => onCellClick(cat, iso)
                  : viewablePhysical
                    ? () => onViewPhysical(iso)
                    : undefined;
                return (
                  <td
                    key={iso}
                    className={`${classes.join(" ")}${viewablePhysical ? " tc-mirror-view" : ""}`}
                    // Overall is auto-generated; future days are not editable.
                    onClick={handleClick}
                    title={title}
                  >
                    {!isRating && (
                      <span className="cell-text">{cell?.display ?? ""}</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
