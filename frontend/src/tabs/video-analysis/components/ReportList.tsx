import type { AnalysisReport } from "../types";
import { ANALYSIS_STATUS_LABEL } from "../labels";

interface Props {
  reports: AnalysisReport[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onDelete: (id: number) => void;
}

const STATUS_CLASS: Record<string, string> = {
  parsing: "va-st-processing",
  awaiting_review: "va-st-await",
  reviewed: "va-st-done",
  error: "va-st-error",
};

export default function ReportList({ reports, selectedId, onSelect, onDelete }: Props) {
  if (reports.length === 0) {
    return <p className="va-muted">Chưa có bản phân tích nào. Dán một bản ở trên để bắt đầu.</p>;
  }
  return (
    <ul className="va-report-list">
      {reports.map((r) => (
        <li
          key={r.id}
          className={`va-report-item${selectedId === r.id ? " active" : ""}`}
          onClick={() => onSelect(r.id)}
        >
          <div className="va-report-main">
            <span className="va-report-date">{r.analysis_date}</span>
            <span className={`va-chip va-set-chip va-set-${r.setting}`}>
              {r.setting === "match" ? "🔥 Đấu" : "🏓 Tập"}
            </span>
            <span className="va-report-title">{r.title}</span>
          </div>
          <div className="va-report-meta">
            <span className={`va-chip va-st-chip ${STATUS_CLASS[r.status] || ""}`}>
              {ANALYSIS_STATUS_LABEL[r.status]}
            </span>
            <button
              className="va-x"
              title="Xóa"
              onClick={(e) => { e.stopPropagation(); onDelete(r.id); }}
            >
              ×
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
