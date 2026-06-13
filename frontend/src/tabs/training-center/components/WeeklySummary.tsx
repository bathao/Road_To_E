import type { Report } from "../types";

/** Coach-voice weekly note + a compact stats strip (data-driven). */
export default function WeeklySummary({ report }: { report: Report }) {
  return (
    <section className="tc-summary">
      <div className="tc-summary-coach">🗣️ {report.summary_vi}</div>
      <div className="tc-summary-stats">
        <span>
          🔥 <b>{report.current_streak}</b> ngày liên tiếp
        </span>
        <span>
          <b>{report.sessions_last_7d}</b> buổi / 7 ngày
        </span>
        <span>
          <b>{report.total_sessions_done}</b> buổi tổng
        </span>
        {report.days_since_last != null && (
          <span>
            Buổi gần nhất: <b>{report.days_since_last}</b> ngày trước
          </span>
        )}
      </div>
    </section>
  );
}
