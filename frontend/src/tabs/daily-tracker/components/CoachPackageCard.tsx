// Coaching package (10-session block) status: how many sessions are left in
// the current package. Range-independent — it's about "now".
import type { CoachPackage } from "../types";
import { prettyDate } from "../../../shared/dates";

function pkgStatusText(p: CoachPackage): string {
  switch (p.status) {
    case "low":
      return `Almost out — ${p.remaining} session${p.remaining === 1 ? "" : "s"} left, renew soon`;
    case "done":
      return "Package used up — time to renew";
    case "over":
      return `Trained ${p.used} (over ${p.size}) — mark the new package's start?`;
    default:
      return `${p.remaining} session${p.remaining === 1 ? "" : "s"} left`;
  }
}

export default function CoachPackageCard({
  current,
  onStartNext,
  busy,
}: {
  current: CoachPackage;
  // Renew action: mark session size+1 as the new package's start.
  onStartNext: () => void;
  busy: boolean;
}) {
  return (
    <div className={`stat-card pkg-card pkg-${current.status}`}>
      <div className="stat-card-title">Coach package</div>
      <div className="stat-big">
        {current.used}
        <span className="stat-of">/{current.size}</span>
      </div>
      <div className="stat-sub">started {prettyDate(current.start_date)}</div>
      <div className="pkg-status">{pkgStatusText(current)}</div>
      {current.status === "over" && (
        <button className="btn primary" onClick={onStartNext} disabled={busy}>
          ★ Start new package from session {current.size + 1}
        </button>
      )}
    </div>
  );
}
