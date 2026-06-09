import { useState } from "react";
import type { Aspect, Report, Skill, SkillIn, SkillStatus } from "../types";
import { ASPECT_LABEL, SKILL_STATUS_LABEL } from "../labels";

interface Props {
  skills: Skill[];
  report: Report | null;
  regenerating: boolean;
  canRegenerate: boolean;
  onRegenerate: () => Promise<void>;
  onUpdateSkill: (aspect: Aspect, payload: SkillIn) => Promise<void>;
}

const STATUS_ORDER: SkillStatus[] = [
  "strength",
  "improving",
  "neutral",
  "needs_work",
  "weakness",
];

// Colour the rating bar by skill status.
const STATUS_CLASS: Record<SkillStatus, string> = {
  strength: "va-sk-strong",
  improving: "va-sk-improving",
  neutral: "va-sk-neutral",
  needs_work: "va-sk-needswork",
  weakness: "va-sk-weak",
};

export default function SkillBoard({
  skills,
  report,
  regenerating,
  canRegenerate,
  onRegenerate,
  onUpdateSkill,
}: Props) {
  const [editing, setEditing] = useState<Aspect | null>(null);
  const [draftRating, setDraftRating] = useState<string>("");
  const [draftStatus, setDraftStatus] = useState<SkillStatus>("neutral");
  const [draftAssessment, setDraftAssessment] = useState<string>("");
  const [saving, setSaving] = useState(false);

  const startEdit = (s: Skill) => {
    setEditing(s.aspect);
    setDraftRating(s.rating == null ? "" : String(s.rating));
    setDraftStatus(s.status);
    setDraftAssessment(s.assessment);
  };

  const saveEdit = async (aspect: Aspect) => {
    setSaving(true);
    try {
      const r = parseInt(draftRating, 10);
      await onUpdateSkill(aspect, {
        rating: draftRating === "" || Number.isNaN(r) ? null : Math.max(1, Math.min(10, r)),
        status: draftStatus,
        assessment: draftAssessment,
      });
      setEditing(null);
    } finally {
      setSaving(false);
    }
  };

  // Evidence per aspect from the report (accepted findings).
  const evidenceFor = (aspect: Aspect): string[] =>
    report?.skills.find((s) => s.aspect === aspect)?.evidence ?? [];

  return (
    <section className="va-card">
      <div className="va-card-head">
        <h3>📊 Hồ sơ kỹ năng</h3>
        <button
          className="btn"
          disabled={regenerating || !canRegenerate}
          title={canRegenerate ? "" : "Cần có nhận xét đã duyệt trước khi dựng hồ sơ"}
          onClick={onRegenerate}
        >
          {regenerating ? "Đang dựng…" : "↻ Cập nhật hồ sơ kỹ năng"}
        </button>
      </div>
      {!canRegenerate && (
        <p className="va-muted">
          Chưa có nhận xét nào được duyệt. Phân tích một clip rồi <b>Duyệt</b> các nhận xét
          đúng, sau đó bấm "Cập nhật hồ sơ kỹ năng".
        </p>
      )}

      <div className="va-skill-list">
        {skills.map((s) => {
          const ev = evidenceFor(s.aspect);
          const isEditing = editing === s.aspect;
          return (
            <div key={s.aspect} className="va-skill-row">
              <div className="va-skill-head">
                <span className="va-skill-name">{ASPECT_LABEL[s.aspect]}</span>
                {isEditing ? (
                  <input
                    className="pb-input va-skill-rating-input"
                    type="number"
                    min={1}
                    max={10}
                    value={draftRating}
                    placeholder="—"
                    onChange={(e) => setDraftRating(e.target.value)}
                  />
                ) : (
                  <span className="va-skill-rating">{s.rating == null ? "—" : `${s.rating}/10`}</span>
                )}
                {isEditing ? (
                  <select
                    className="pb-select"
                    value={draftStatus}
                    onChange={(e) => setDraftStatus(e.target.value as SkillStatus)}
                  >
                    {STATUS_ORDER.map((st) => (
                      <option key={st} value={st}>{SKILL_STATUS_LABEL[st]}</option>
                    ))}
                  </select>
                ) : (
                  <span className={`va-chip va-sk-chip ${STATUS_CLASS[s.status]}`}>
                    {SKILL_STATUS_LABEL[s.status]}
                  </span>
                )}
                {isEditing ? (
                  <span className="va-row-gap">
                    <button className="btn primary" disabled={saving}
                      onClick={() => saveEdit(s.aspect)}>{saving ? "…" : "Lưu"}</button>
                    <button className="btn" disabled={saving}
                      onClick={() => setEditing(null)}>Hủy</button>
                  </span>
                ) : (
                  <button className="va-x" title="Sửa tay" onClick={() => startEdit(s)}>✎</button>
                )}
              </div>

              <div className="va-skill-bar">
                <div
                  className={`va-skill-bar-fill ${STATUS_CLASS[s.status]}`}
                  style={{ width: `${((s.rating ?? 0) / 10) * 100}%` }}
                />
              </div>

              {isEditing ? (
                <textarea
                  className="pb-input va-skill-assess-edit"
                  value={draftAssessment}
                  placeholder="Đánh giá ngắn cho mảng này…"
                  onChange={(e) => setDraftAssessment(e.target.value)}
                />
              ) : (
                s.assessment && <p className="va-skill-assess">{s.assessment}</p>
              )}

              {!isEditing && ev.length > 0 && (
                <ul className="va-skill-evidence">
                  {ev.map((t, i) => <li key={i}>{t}</li>)}
                </ul>
              )}
            </div>
          );
        })}
      </div>

      {report && report.improvement_priorities.length > 0 && (
        <div className="va-priorities">
          <h4>🎯 Ưu tiên cải thiện</h4>
          <ol className="va-priority-list">
            {report.improvement_priorities.map((p, i) => <li key={i}>{p}</li>)}
          </ol>
        </div>
      )}

      {report && report.metric_trends.length > 0 && (
        <div className="va-priorities">
          <h4>📈 Tiến bộ chỉ số (clip mới nhất vs trước)</h4>
          <ul className="va-trend-list">
            {report.metric_trends.map((t) => {
              const cls =
                t.trend === "improved" ? "va-trend-up"
                : t.trend === "declined" ? "va-trend-down" : "va-trend-flat";
              const arrow = t.delta > 0 ? "▲" : t.delta < 0 ? "▼" : "■";
              const amt = t.pct != null
                ? `${t.pct > 0 ? "+" : ""}${t.pct}%`
                : `${t.delta > 0 ? "+" : ""}${t.delta}`;
              return (
                <li key={t.name}>
                  <span>{t.label}: <b>{t.current}{t.unit}</b></span>
                  <span className={`va-trend ${cls}`}>{arrow} {amt}</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
