import { useEffect, useState } from "react";
import type { Profile, ProfileIn } from "../types";

interface Props {
  profile: Profile;
  onSave: (payload: ProfileIn) => Promise<void>;
  onRegenerate: () => Promise<void>;
  regenerating: boolean;
  canRegenerate: boolean;
}

const SUMMARY_FIELDS: { key: keyof Profile; label: string }[] = [
  { key: "overall_summary", label: "Overview" },
  { key: "strengths_summary", label: "Strengths" },
  { key: "weaknesses_summary", label: "Weaknesses" },
  { key: "serve_summary", label: "Serve" },
  { key: "footwork_summary", label: "Footwork" },
  { key: "posture_summary", label: "Stance / posture" },
];

export default function ProfilePanel({
  profile,
  onSave,
  onRegenerate,
  regenerating,
  canRegenerate,
}: Props) {
  const [draft, setDraft] = useState<Profile>(profile);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    setDraft(profile);
  }, [profile]);

  const set = (patch: Partial<Profile>) => setDraft((d) => ({ ...d, ...patch }));

  const save = async () => {
    await onSave({
      name: draft.name,
      handed: draft.handed,
      grip: draft.grip,
      style: draft.style,
      equipment: draft.equipment,
      physique: draft.physique,
    });
    setEditing(false);
  };

  return (
    <section className="va-card va-profile">
      <div className="va-card-head">
        <h3>👤 Profile: {profile.name}</h3>
        {editing ? (
          <div className="va-row-gap">
            <button className="btn" onClick={() => { setDraft(profile); setEditing(false); }}>
              Cancel
            </button>
            <button className="btn primary" onClick={save}>Save</button>
          </div>
        ) : (
          <button className="btn" onClick={() => setEditing(true)}>Edit</button>
        )}
      </div>

      {editing ? (
        <div className="va-form-grid">
          <label>Name<input className="pb-input" value={draft.name}
            onChange={(e) => set({ name: e.target.value })} /></label>
          <label>Handedness
            <select className="pb-select" value={draft.handed}
              onChange={(e) => set({ handed: e.target.value })}>
              <option value="right">Right</option>
              <option value="left">Left</option>
            </select>
          </label>
          <label>Grip
            <select className="pb-select" value={draft.grip}
              onChange={(e) => set({ grip: e.target.value })}>
              <option value="shakehand">Shakehand</option>
              <option value="penhold">Penhold</option>
            </select>
          </label>
          <label>Play style<input className="pb-input" value={draft.style}
            placeholder="offensive, defensive, all-round…"
            onChange={(e) => set({ style: e.target.value })} /></label>
          <label className="va-col-span">Equipment (blade + rubbers)<input className="pb-input"
            value={draft.equipment} onChange={(e) => set({ equipment: e.target.value })} /></label>
          <label className="va-col-span">Physique (height / build)<input className="pb-input"
            value={draft.physique} onChange={(e) => set({ physique: e.target.value })} /></label>
        </div>
      ) : (
        <div className="va-basics">
          <span className="va-chip">Handedness: {draft.handed === "left" ? "Left" : "Right"}</span>
          <span className="va-chip">Grip: {draft.grip === "penhold" ? "Penhold" : "Shakehand"}</span>
          {draft.style && <span className="va-chip">Style: {draft.style}</span>}
          {draft.equipment && <span className="va-chip">Equipment: {draft.equipment}</span>}
          {draft.physique && <span className="va-chip">Physique: {draft.physique}</span>}
        </div>
      )}

      <div className="va-card-head va-mt">
        <h4>Synthesized profile (AI)</h4>
        <button
          className="btn"
          disabled={regenerating || !canRegenerate}
          title={canRegenerate ? "" : "Approved findings are required before synthesizing"}
          onClick={onRegenerate}
        >
          {regenerating ? "Synthesizing…" : "↻ Re-synthesize from findings"}
        </button>
      </div>
      {!canRegenerate && (
        <p className="va-muted">
          No approved findings to synthesize yet. Paste an analysis, approve the correct
          findings, then click "Re-synthesize".
        </p>
      )}
      <div className="va-summaries">
        {SUMMARY_FIELDS.map(({ key, label }) => {
          const value = (profile[key] as string) || "";
          return (
            <div key={key} className="va-summary-item">
              <div className="va-summary-label">{label}</div>
              <div className={`va-summary-text${value ? "" : " va-muted"}`}>
                {value || "— none yet —"}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
