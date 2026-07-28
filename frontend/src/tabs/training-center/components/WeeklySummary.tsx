import type { Report } from "../types";

/** Coach-voice weekly note + a compact stats strip (data-driven). */
export default function WeeklySummary({ report }: { report: Report }) {
  return (
    <section className="tc-summary">
      <div className="tc-summary-coach">🗣️ {report.summary_vi}</div>
      <div className="tc-summary-stats">
        <span>
          🔥 <b>{report.current_streak}</b> day streak
        </span>
        <span>
          <b>{report.sessions_last_7d}</b> sessions / 7 days
        </span>
        <span>
          <b>{report.total_sessions_done}</b> sessions total
        </span>
        {report.days_since_last != null && (
          <span>
            Last session: <b>{report.days_since_last}</b> days ago
          </span>
        )}
      </div>
    </section>
  );
}
