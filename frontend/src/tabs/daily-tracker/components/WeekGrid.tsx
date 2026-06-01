import type { Category, WeekResponse } from "../types";
import { cellKey } from "../types";
import { dayHeader, todayIso } from "../dates";

// The Excel-like weekly grid. Rows = categories, columns = 7 days.
// Clicking any cell opens the matching editor for that (category, date).
export default function WeekGrid({
  week,
  onCellClick,
}: {
  week: WeekResponse;
  onCellClick: (category: Category, dateIso: string) => void;
}) {
  const today = todayIso();

  return (
    <div className="grid-wrap">
      <table className="week-grid">
        <thead>
          <tr>
            <th className="corner">Category</th>
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
                // Future days can't be logged yet — only today and the past.
                const isFuture = iso > today;
                const editable = !isRating && !isFuture;
                const classes = ["cell", `type-${cat.type}`];
                if (isToday) classes.push("today");
                if (isRating) classes.push("readonly");
                if (isFuture) classes.push("future");
                // Fill the whole cell background with the day's color
                // (Overall row, and Physical Training when >=70% ticked).
                if (cell?.color) classes.push(`rating-${cell.color}`);
                return (
                  <td
                    key={iso}
                    className={classes.join(" ")}
                    // Overall is auto-generated; future days are not editable.
                    onClick={editable ? () => onCellClick(cat, iso) : undefined}
                    title={
                      isFuture
                        ? "Future date — you can only log today and past days"
                        : isRating
                          ? "Auto-generated from the day's data"
                          : undefined
                    }
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
