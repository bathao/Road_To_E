import { addDays, toIso } from "../../../shared/dates";

// A compact "last 5 weeks" training heatmap + current streak.
export default function Heatmap({
  doneDates,
  streak,
}: {
  doneDates: string[];
  streak: number;
}) {
  const trained = new Set(doneDates);
  const today = new Date();
  const days: { iso: string; on: boolean; isToday: boolean }[] = [];
  for (let i = 34; i >= 0; i--) {
    const iso = toIso(addDays(today, -i));
    days.push({ iso, on: trained.has(iso), isToday: i === 0 });
  }
  return (
    <div className="tc-heat">
      <div className="tc-heat-head">
        <span className="tc-heat-streak">🔥 {streak} day streak</span>
        <span className="tc-muted tc-heat-sub">Last 35 days</span>
      </div>
      <div className="tc-heat-grid">
        {days.map((d) => (
          <span
            key={d.iso}
            className={`tc-heat-cell${d.on ? " on" : ""}${d.isToday ? " today" : ""}`}
            title={`${d.iso}${d.on ? " · trained" : ""}`}
          />
        ))}
      </div>
    </div>
  );
}
