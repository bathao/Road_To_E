import type { ReactNode } from "react";
import { fmtDelta } from "../format";

// The ±Δ pill every tab tags ELO movements with (green up / red down —
// .elo-chip lives in base.css). One source for the sign/class logic; it had
// drifted into five hand-rolled copies. `children` appends extra text after
// the delta (e.g. " · 12 matches").
export default function EloDeltaChip({
  delta,
  title,
  children,
}: {
  delta: number;
  title?: string;
  children?: ReactNode;
}) {
  return (
    <span
      className={`elo-chip ${delta >= 0 ? "elo-up" : "elo-down"}`}
      title={title}
    >
      {fmtDelta(delta)}
      {children}
    </span>
  );
}
