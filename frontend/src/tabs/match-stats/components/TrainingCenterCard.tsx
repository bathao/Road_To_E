// Snapshot of the off-table physical program (Training Center tab). Moved
// from the retired Profile tab 2026-07-30; rangeless — always the latest.
import type { Report as TrainingReport } from "../../training-center/types";

export default function TrainingCenterCard({
  report,
}: {
  report: TrainingReport | null;
}) {
  return (
    <section className="stats-card">
      <h3>💪 Training Center</h3>
      {report && report.total_sessions_done > 0 ? (
        <>
          <p className="va-muted">{report.summary_vi}</p>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-card-title">Level</div>
              <div className="stat-big" style={{ fontSize: "1.3rem" }}>
                {report.current_level_vi}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Sessions completed</div>
              <div className="stat-big">{report.total_sessions_done}</div>
              <div className="stat-line muted">
                <span>{report.sessions_last_7d} sessions / 7 days</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Last session</div>
              <div className="stat-big">{report.days_since_last ?? "—"}</div>
              <div className="stat-line muted">
                <span>days ago</span>
              </div>
            </div>
          </div>
          <div className="prof-cat-list">
            {(["legs", "core", "balance"] as const).map((k) => (
              <div key={k} className="stat-line">
                <span>
                  {k === "legs" ? "🦵 Legs" : k === "core" ? "🌀 Core" : "⚖️ Balance"}
                </span>
                <span>{report.day_type_counts[k] ?? 0} sessions</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="va-muted">
          No sessions yet. Open the Training Center tab 💪 to get started.
        </p>
      )}
    </section>
  );
}
