export interface Bar {
  label: string;
  value: number; // numeric height driver
  display: string; // text shown above the bar
  title?: string; // native hover tooltip (bar chart)
  tip?: string; // rich-tooltip heading (line chart)
  highlight?: boolean;
}

// A dependency-free vertical bar chart. Heights are scaled to the max value;
// all-zero data renders flat baselines.
export default function BarChart({ bars }: { bars: Bar[] }) {
  const max = Math.max(0, ...bars.map((b) => b.value));

  return (
    <div className="barchart">
      {bars.map((b) => {
        const h = max > 0 ? (b.value / max) * 100 : 0;
        return (
          <div className="bar-col" key={b.label} title={b.title ?? b.label}>
            <div className="bar-value">{b.value ? b.display : ""}</div>
            <div className="bar-track">
              <div
                className={`bar-fill${b.highlight ? " highlight" : ""}`}
                style={{ height: `${h}%` }}
              />
            </div>
            <div className="bar-label">{b.label}</div>
          </div>
        );
      })}
    </div>
  );
}
