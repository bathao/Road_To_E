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
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate()
    ).padStart(2, "0")}`;
    days.push({ iso, on: trained.has(iso), isToday: i === 0 });
  }
  return (
    <div className="tc-heat">
      <div className="tc-heat-head">
        <span className="tc-heat-streak">🔥 {streak} ngày liên tiếp</span>
        <span className="tc-muted tc-heat-sub">35 ngày gần đây</span>
      </div>
      <div className="tc-heat-grid">
        {days.map((d) => (
          <span
            key={d.iso}
            className={`tc-heat-cell${d.on ? " on" : ""}${d.isToday ? " today" : ""}`}
            title={`${d.iso}${d.on ? " · đã tập" : ""}`}
          />
        ))}
      </div>
    </div>
  );
}
