import { useState } from "react";
import type { Aspect, Report, Setting, Skill, SkillIn, SkillStatus } from "../types";
import {
  ASPECT_LABEL,
  ASPECT_ORDER,
  SETTING_LABEL,
  SKILL_STATUS_CLASS as STATUS_CLASS,
  SKILL_STATUS_LABEL,
} from "../labels";

interface Props {
  skills: Skill[];
  report: Report | null;
  regenerating: boolean;
  canRegenerate: boolean;
  onRegenerate: () => Promise<void>;
  onUpdateSkill: (aspect: Aspect, setting: Setting, payload: SkillIn) => Promise<void>;
}

const STATUS_ORDER: SkillStatus[] = [
  "strength",
  "improving",
  "neutral",
  "needs_work",
  "weakness",
];

const SETTINGS: Setting[] = ["practice", "match"];
const SETTING_ICON: Record<Setting, string> = { practice: "🏓", match: "🔥" };

export default function SkillBoard({
  skills,
  report,
  regenerating,
  canRegenerate,
  onRegenerate,
  onUpdateSkill,
}: Props) {
  // editing key = `${aspect}|${setting}`
  const [editing, setEditing] = useState<string | null>(null);
  const [draftRating, setDraftRating] = useState<string>("");
  const [draftStatus, setDraftStatus] = useState<SkillStatus>("neutral");
  const [draftAssessment, setDraftAssessment] = useState<string>("");
  const [saving, setSaving] = useState(false);

  // Group the ledger by aspect → { practice, match }.
  const byAspect = new Map<Aspect, Partial<Record<Setting, Skill>>>();
  for (const s of skills) {
    const g = byAspect.get(s.aspect) ?? {};
    g[s.setting] = s;
    byAspect.set(s.aspect, g);
  }
  const aspects = ASPECT_ORDER.filter((a) => byAspect.has(a));

  const startEdit = (s: Skill) => {
    setEditing(`${s.aspect}|${s.setting}`);
    setDraftRating(s.rating == null ? "" : String(s.rating));
    setDraftStatus(s.status);
    setDraftAssessment(s.assessment);
  };

  const saveEdit = async (aspect: Aspect, setting: Setting) => {
    setSaving(true);
    try {
      const r = parseInt(draftRating, 10);
      await onUpdateSkill(aspect, setting, {
        rating: draftRating === "" || Number.isNaN(r) ? null : Math.max(1, Math.min(10, r)),
        status: draftStatus,
        assessment: draftAssessment,
      });
      setEditing(null);
    } finally {
      setSaving(false);
    }
  };

  const evidenceFor = (aspect: Aspect, setting: Setting): string[] =>
    report?.skills.find((s) => s.aspect === aspect && s.setting === setting)?.evidence ?? [];

  const renderSetting = (aspect: Aspect, setting: Setting, s: Skill | undefined) => {
    if (!s) return null;
    const key = `${aspect}|${setting}`;
    const isEditing = editing === key;
    const ev = evidenceFor(aspect, setting);
    return (
      <div key={key} className="va-skill-setting">
        <div className="va-skill-head">
          <span className="va-skill-setname">
            {SETTING_ICON[setting]} {SETTING_LABEL[setting]}
          </span>
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
                onClick={() => saveEdit(aspect, setting)}>{saving ? "…" : "Save"}</button>
              <button className="btn" disabled={saving}
                onClick={() => setEditing(null)}>Cancel</button>
            </span>
          ) : (
            <button className="va-x" title="Edit manually" onClick={() => startEdit(s)}>✎</button>
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
            placeholder="Short assessment for this area…"
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
  };

  return (
    <section className="va-card">
      <div className="va-card-head">
        <h3>📊 Skill profile (Practice vs Match)</h3>
        <button
          className="btn"
          disabled={regenerating || !canRegenerate}
          title={canRegenerate ? "" : "Approved findings are required before building the profile"}
          onClick={onRegenerate}
        >
          {regenerating ? "Building…" : "↻ Update skill profile"}
        </button>
      </div>
      {!canRegenerate && (
        <p className="va-muted">
          No approved findings yet. Paste an analysis (Practice / Match), then click
          "Update skill profile".
        </p>
      )}

      <div className="va-skill-list">
        {aspects.map((a) => {
          const g = byAspect.get(a)!;
          return (
            <div key={a} className="va-skill-row">
              <div className="va-skill-name">{ASPECT_LABEL[a]}</div>
              <div className="va-skill-settings">
                {SETTINGS.map((st) => renderSetting(a, st, g[st]))}
              </div>
            </div>
          );
        })}
      </div>

      {report && report.improvement_priorities.length > 0 && (
        <div className="va-priorities">
          <h4>🎯 Improvement priorities</h4>
          <ol className="va-priority-list">
            {report.improvement_priorities.map((p, i) => <li key={i}>{p}</li>)}
          </ol>
        </div>
      )}

      {report && (() => {
        // Per (aspect, setting) development: first → latest dated rating point.
        const moves = report.skill_history
          .map((h) => {
            const pts = h.points.filter((p) => p.rating != null);
            if (pts.length < 2) return null;
            return { aspect: h.aspect, setting: h.setting, first: pts[0], last: pts[pts.length - 1] };
          })
          .filter((m): m is NonNullable<typeof m> => m !== null);
        if (moves.length === 0) return null;
        return (
          <div className="va-priorities">
            <h4>📈 Skill progress over time</h4>
            <ul className="va-trend-list">
              {moves.map((m) => {
                const delta = (m.last.rating ?? 0) - (m.first.rating ?? 0);
                const cls =
                  delta > 0 ? "va-trend-up" : delta < 0 ? "va-trend-down" : "va-trend-flat";
                const arrow = delta > 0 ? "▲" : delta < 0 ? "▼" : "■";
                return (
                  <li key={`${m.aspect}|${m.setting}`}>
                    <span>
                      {ASPECT_LABEL[m.aspect]} <span className="va-muted">[{SETTING_LABEL[m.setting]}]</span>:{" "}
                      <b>{m.first.rating}/10</b> <span className="va-muted">({m.first.analysis_date})</span>
                      {" → "}
                      <b>{m.last.rating}/10</b> <span className="va-muted">({m.last.analysis_date})</span>
                    </span>
                    <span className={`va-trend ${cls}`}>{arrow} {delta > 0 ? "+" : ""}{delta}</span>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })()}

      {report && report.practice_vs_match.length > 0 && (
        <div className="va-priorities">
          <h4>🆚 Practice vs Match (finding counts)</h4>
          <ul className="va-pvm-list">
            {report.practice_vs_match.map((s) => {
              const gap = s.practice_strengths > 0 && s.match_weaknesses > 0;
              return (
                <li key={s.aspect} className={gap ? "va-pvm-gap" : ""}>
                  <span className="va-pvm-name">{ASPECT_LABEL[s.aspect]}</span>
                  <span className="va-pvm-cell">
                    🏓 <b className="va-strength">{s.practice_strengths}↑</b>{" "}
                    <b className="va-weakness">{s.practice_weaknesses}↓</b>
                  </span>
                  <span className="va-pvm-cell">
                    🔥 <b className="va-strength">{s.match_strengths}↑</b>{" "}
                    <b className="va-weakness">{s.match_weaknesses}↓</b>
                  </span>
                  {gap && <span className="va-pvm-flag" title="Good in practice, weak in matches">⚠️ gap</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
