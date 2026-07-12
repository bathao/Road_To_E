import { useEffect, useState } from "react";
import type {
  AnalysisReportDetail,
  Aspect,
  FindingDecision,
  Polarity,
} from "../types";
import { ASPECT_LABEL, ASPECT_ORDER, ANALYSIS_STATUS_LABEL, POLARITY_LABEL, SETTING_LABEL } from "../labels";

interface Props {
  detail: AnalysisReportDetail;
  reviewing: boolean;
  onReview: (decisions: FindingDecision[]) => Promise<void>;
  onDelete: () => void;
}

interface Draft {
  accept: boolean;
  text: string;
  aspect: Aspect;
  polarity: Polarity;
}

export default function ReviewPanel({ detail, reviewing, onReview, onDelete }: Props) {
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [showSource, setShowSource] = useState(false);

  // Start fresh when a DIFFERENT report is selected…
  useEffect(() => {
    setDrafts({});
  }, [detail.id]);

  // …then seed drafts for findings that don't have one yet. Merging (instead
  // of replacing) keeps in-progress edits alive while the 2.5s parsing poll
  // refreshes `detail` — replacing on every poll used to wipe the textareas.
  useEffect(() => {
    setDrafts((prev) => {
      const next = { ...prev };
      for (const t of detail.traits) {
        if (!next[t.id]) {
          next[t.id] = {
            accept: t.status !== "rejected",
            text: t.text,
            aspect: t.aspect,
            polarity: t.polarity,
          };
        }
      }
      return next;
    });
  }, [detail.id, detail.traits]);

  const set = (id: number, patch: Partial<Draft>) =>
    setDrafts((d) => ({ ...d, [id]: { ...d[id], ...patch } }));

  const submit = async () => {
    const decisions: FindingDecision[] = detail.traits.map((t) => {
      const d = drafts[t.id];
      return {
        id: t.id,
        accept: d.accept,
        text: d.text,
        aspect: d.aspect,
        polarity: d.polarity,
      };
    });
    await onReview(decisions);
  };

  return (
    <section className="va-card">
      <div className="va-card-head">
        <h3>
          {detail.analysis_date} · {detail.title}
        </h3>
        <div className="va-row-gap">
          <span className={`va-chip va-set-chip va-set-${detail.setting}`}>
            {detail.setting === "match" ? "🔥 " : "🏓 "}{SETTING_LABEL[detail.setting]}
          </span>
          <span className="va-chip">{ANALYSIS_STATUS_LABEL[detail.status]}</span>
          <button className="va-x" title="Xóa bản phân tích" onClick={onDelete}>×</button>
        </div>
      </div>

      {detail.context && <p className="va-muted">Bối cảnh: {detail.context}</p>}
      {detail.status === "error" && (
        <div className="va-warn">⚠️ {detail.error_msg || "Bóc tách lỗi."}</div>
      )}
      {detail.status === "parsing" && (
        <p className="va-muted">Đang bóc tách nhận xét từ văn bản…</p>
      )}

      <button className="va-link" onClick={() => setShowSource((s) => !s)}>
        {showSource ? "▾ Ẩn văn bản gốc" : "▸ Xem văn bản gốc"}
      </button>
      {showSource && <pre className="va-source-text">{detail.source_text}</pre>}

      {detail.traits.length === 0 ? (
        detail.status !== "parsing" && (
          <p className="va-muted">Không bóc tách được nhận xét nào từ văn bản này.</p>
        )
      ) : (
        <>
          <div className="va-card-head va-mt">
            <h4>Nhận xét đã lưu ({detail.traits.length})</h4>
            <span className="va-muted">Đã tự lưu. Sửa nội dung hoặc bỏ tick để loại nếu cần.</span>
          </div>
          <div className="va-review-list">
            {detail.traits.map((t) => {
              const d = drafts[t.id];
              if (!d) return null;
              return (
                <div key={t.id} className={`va-review-row${d.accept ? "" : " va-dropped"}`}>
                  <input
                    type="checkbox"
                    checked={d.accept}
                    onChange={(e) => set(t.id, { accept: e.target.checked })}
                  />
                  <div className="va-review-body">
                    <textarea
                      className="pb-input"
                      value={d.text}
                      rows={2}
                      onChange={(e) => set(t.id, { text: e.target.value })}
                    />
                    <div className="va-review-tags">
                      <select
                        className="pb-select"
                        value={d.aspect}
                        onChange={(e) => set(t.id, { aspect: e.target.value as Aspect })}
                      >
                        {ASPECT_ORDER.map((a) => (
                          <option key={a} value={a}>{ASPECT_LABEL[a]}</option>
                        ))}
                      </select>
                      <select
                        className="pb-select"
                        value={d.polarity}
                        onChange={(e) => set(t.id, { polarity: e.target.value as Polarity })}
                      >
                        <option value="strength">{POLARITY_LABEL.strength}</option>
                        <option value="weakness">{POLARITY_LABEL.weakness}</option>
                        <option value="neutral">{POLARITY_LABEL.neutral}</option>
                      </select>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="va-row-end">
            <button className="btn primary" disabled={reviewing} onClick={submit}>
              {reviewing ? "Đang lưu…" : "Lưu chỉnh sửa"}
            </button>
          </div>
        </>
      )}
    </section>
  );
}
