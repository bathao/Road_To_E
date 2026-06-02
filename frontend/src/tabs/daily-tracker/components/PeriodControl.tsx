import type { Mode } from "../period";
import { MODES, MODE_LABEL } from "../period";

// The single timeline control shared by the grid and the Analysis panel.
export default function PeriodControl({
  mode,
  label,
  customFrom,
  customTo,
  onMode,
  onStep,
  onToday,
  onCustomFrom,
  onCustomTo,
}: {
  mode: Mode;
  label: string;
  customFrom: string;
  customTo: string;
  onMode: (m: Mode) => void;
  onStep: (dir: number) => void;
  onToday: () => void;
  onCustomFrom: (iso: string) => void;
  onCustomTo: (iso: string) => void;
}) {
  return (
    <div className="period-control">
      <div className="seg">
        {MODES.map((m) => (
          <button
            key={m}
            className={`seg-btn${mode === m ? " active" : ""}`}
            onClick={() => onMode(m)}
          >
            {MODE_LABEL[m]}
          </button>
        ))}
      </div>

      {mode === "custom" ? (
        <div className="custom-range">
          <input
            type="date"
            value={customFrom}
            onChange={(e) => onCustomFrom(e.target.value)}
          />
          <span>→</span>
          <input
            type="date"
            value={customTo}
            onChange={(e) => onCustomTo(e.target.value)}
          />
        </div>
      ) : (
        <div className="analysis-nav">
          <button className="btn" onClick={() => onStep(-1)} aria-label="Previous">
            ◀
          </button>
          <button className="btn" onClick={onToday}>
            Today
          </button>
          <button className="btn" onClick={() => onStep(1)} aria-label="Next">
            ▶
          </button>
          <span className="analysis-range">{label}</span>
        </div>
      )}
    </div>
  );
}
