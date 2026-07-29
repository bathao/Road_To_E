// Training discipline over the selected range: days trained, total time and
// the per-category minutes list.
import { fmtMinutes } from "../../../shared/format";
import type { TrackerStats } from "../types";

export default function TrainingDisciplineCard({ training }: { training: TrackerStats | null }) {
  return (
    <section className="va-card">
      <h3>🏋️ Training discipline</h3>
      {training ? (
        <>
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-card-title">Days trained</div>
              <div className="stat-big">{training.days_trained}</div>
              <div className="stat-line muted">
                <span>of {training.num_days} days</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Total time</div>
              <div className="stat-big">{(training.minutes_total / 60).toFixed(1)}h</div>
              <div className="stat-line muted">
                <span>{fmtMinutes(training.minutes_total)}</span>
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card-title">Fitness sessions</div>
              <div className="stat-big">{training.days_physical}</div>
              <div className="stat-line muted">
                <span>days with fitness work</span>
              </div>
            </div>
          </div>
          {training.minutes_by_category.length > 0 && (
            <div className="prof-cat-list">
              {training.minutes_by_category.map((c) => (
                <div key={c.key} className="stat-line">
                  <span>{c.label}</span>
                  <span>{fmtMinutes(c.minutes)}</span>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <p className="va-muted">Loading…</p>
      )}
    </section>
  );
}
