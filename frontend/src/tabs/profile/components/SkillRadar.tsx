import type { Aspect, Skill } from "../../video-analysis/types";

interface Props {
  skills: Skill[];
}

// Short labels for the cramped radar; the bar list shows the full names.
const SHORT_LABEL: Record<Aspect, string> = {
  serve: "Giao bóng",
  receive: "Đỡ giao",
  forehand: "Thuận tay",
  backhand: "Trái tay",
  footwork: "Bộ chân",
  stance_posture: "Tư thế",
  tactics: "Chiến thuật",
  mental: "Tâm lý",
  physical: "Thể lực",
  other: "Khác",
};

// A hand-rolled radar/spider chart (the project has no charting library).
// One axis per skill aspect, value = rating / 10. The viewBox is padded well
// beyond the chart so the outer axis labels never clip.
const SIZE = 320;
const C = SIZE / 2; // centre
const R = 112; // outer radius
const PAD_X = 56; // horizontal padding for side labels
const PAD_Y = 16; // vertical padding for top/bottom labels
const RINGS = [0.2, 0.4, 0.6, 0.8, 1]; // grid rings at 2/4/6/8/10

// Point on an axis: i-th of n, at fraction f (0..1) of the radius. First axis
// points straight up; the rest go clockwise.
function point(i: number, n: number, f: number) {
  const angle = -Math.PI / 2 + (i / n) * 2 * Math.PI;
  return {
    x: C + Math.cos(angle) * R * f,
    y: C + Math.sin(angle) * R * f,
  };
}

const polygon = (n: number, f: number) =>
  Array.from({ length: n }, (_, i) => {
    const p = point(i, n, f);
    return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }).join(" ");

export default function SkillRadar({ skills }: Props) {
  const n = skills.length;
  if (n < 3) return null;

  const dataPoints = skills.map((s, i) => point(i, n, (s.rating ?? 0) / 10));
  const dataPoly = dataPoints.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");

  return (
    <svg
      className="radar"
      viewBox={`${-PAD_X} ${-PAD_Y} ${SIZE + PAD_X * 2} ${SIZE + PAD_Y * 2}`}
      role="img"
      aria-label="Biểu đồ kỹ năng"
    >
      {/* grid rings */}
      {RINGS.map((f) => (
        <polygon key={f} className="radar-ring" points={polygon(n, f)} />
      ))}
      {/* axes */}
      {skills.map((_, i) => {
        const p = point(i, n, 1);
        return <line key={i} className="radar-axis" x1={C} y1={C} x2={p.x} y2={p.y} />;
      })}
      {/* data polygon */}
      <polygon className="radar-area" points={dataPoly} />
      {dataPoints.map((p, i) => (
        <circle key={i} className="radar-dot" cx={p.x} cy={p.y} r={3} />
      ))}
      {/* axis labels */}
      {skills.map((s, i) => {
        const lp = point(i, n, 1.18);
        const anchor = lp.x < C - 6 ? "end" : lp.x > C + 6 ? "start" : "middle";
        return (
          <text
            key={s.aspect}
            className="radar-label"
            x={lp.x}
            y={lp.y}
            textAnchor={anchor}
            dominantBaseline="middle"
          >
            {SHORT_LABEL[s.aspect as Aspect] ?? s.aspect}
            <tspan className="radar-label-val" dx={4}>
              {s.rating == null ? "" : ` ${s.rating}`}
            </tspan>
          </text>
        );
      })}
    </svg>
  );
}
