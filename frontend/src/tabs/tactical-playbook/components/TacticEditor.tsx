import { useState } from "react";
import type { PhaseKey, PlaybookMeta, TacticIn } from "../types";

// Add/edit form for a tactic. Shared by the "+ Add" button and card editing.
// `initial` carries either an existing tactic's fields or just a pre-filled
// phase for a fresh entry.
export default function TacticEditor({
  initial,
  meta,
  onSave,
  onCancel,
}: {
  initial: TacticIn;
  meta: PlaybookMeta;
  onSave: (payload: TacticIn) => void;
  onCancel: () => void;
}) {
  const [phase, setPhase] = useState<PhaseKey>(initial.phase);
  const [title, setTitle] = useState(initial.title ?? "");
  const [whenToUse, setWhenToUse] = useState(initial.when_to_use ?? "");
  const [howTo, setHowTo] = useState(initial.how_to ?? "");
  const [followUp, setFollowUp] = useState(initial.follow_up ?? "");
  const [risk, setRisk] = useState(initial.risk ?? "");
  const [tags, setTags] = useState<string[]>(initial.tags ?? []);
  const [opponents, setOpponents] = useState<string[]>(
    initial.opponent_styles ?? []
  );
  const [confidence, setConfidence] = useState(initial.confidence ?? 0);
  const [isFavorite, setIsFavorite] = useState(initial.is_favorite ?? false);

  const toggle = (
    list: string[],
    set: (v: string[]) => void,
    value: string
  ) => {
    const v = value.trim();
    if (!v) return;
    set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  };

  const save = () => {
    if (!title.trim()) return;
    onSave({
      phase,
      title: title.trim(),
      when_to_use: whenToUse.trim() || null,
      how_to: howTo.trim() || null,
      follow_up: followUp.trim() || null,
      risk: risk.trim() || null,
      tags,
      opponent_styles: opponents,
      confidence,
      is_favorite: isFavorite,
      source_key: initial.source_key ?? null,
    });
  };

  const tagVocab = [...meta.spin_tags, ...meta.placement_tags];

  return (
    <div className="editor pb-editor">
      <div className="pb-area-row pb-phase-row">
        <span className="editor-sub">Giai đoạn (phase)</span>
        <div className="chip-row">
          {meta.phases.map((p) => (
            <button
              key={p.key}
              type="button"
              className={`chip pb-chip-pick${phase === p.key ? " active" : ""}`}
              onClick={() => setPhase(p.key)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      <input
        className="pb-input"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="Tên chiến thuật (vd: Giao ngắn xoáy xuống vào BH)"
        autoFocus
      />

      <FieldArea label="When — khi nào dùng" value={whenToUse} onChange={setWhenToUse} />
      <FieldArea label="How — cách triển khai" value={howTo} onChange={setHowTo} />
      <FieldArea label="Next — quả tiếp theo" value={followUp} onChange={setFollowUp} />
      <FieldArea label="Risk — rủi ro" value={risk} onChange={setRisk} />

      <ChipPicker
        label="Tags (xoáy / điểm rơi)"
        vocab={tagVocab}
        selected={tags}
        onToggle={(v) => toggle(tags, setTags, v)}
      />

      <ChipPicker
        label="Đối thủ phù hợp"
        vocab={meta.opponent_styles}
        selected={opponents}
        onToggle={(v) => toggle(opponents, setOpponents, v)}
      />

      <div className="pb-form-row">
        <span className="seg-label">Mức tự tin</span>
        <div className="pb-star-pick">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              className={`pb-star-btn${n <= confidence ? " on" : ""}`}
              title={`${n}/5`}
              onClick={() => setConfidence(n === confidence ? 0 : n)}
            >
              ★
            </button>
          ))}
        </div>
        <label className="pb-fav-toggle">
          <input
            type="checkbox"
            checked={isFavorite}
            onChange={(e) => setIsFavorite(e.target.checked)}
          />
          Ghim yêu thích
        </label>
      </div>

      <div className="note-actions">
        <button className="btn" onClick={onCancel}>
          Huỷ
        </button>
        <button className="btn primary" onClick={save} disabled={!title.trim()}>
          Lưu
        </button>
      </div>
    </div>
  );
}

function FieldArea({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="pb-area-row">
      <span className="editor-sub">{label}</span>
      <textarea
        className="note-area pb-area"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={2}
      />
    </label>
  );
}

function ChipPicker({
  label,
  vocab,
  selected,
  onToggle,
}: {
  label: string;
  vocab: string[];
  selected: string[];
  onToggle: (v: string) => void;
}) {
  const [custom, setCustom] = useState("");
  // Show suggested vocab plus any custom selections not already in the vocab.
  const extras = selected.filter((s) => !vocab.includes(s));
  const all = [...vocab, ...extras];

  const addCustom = () => {
    if (custom.trim()) {
      onToggle(custom.trim());
      setCustom("");
    }
  };

  return (
    <div className="pb-area-row">
      <span className="editor-sub">{label}</span>
      <div className="chip-row">
        {all.map((v) => (
          <button
            key={v}
            className={`chip pb-chip-pick${selected.includes(v) ? " active" : ""}`}
            onClick={() => onToggle(v)}
          >
            {v}
          </button>
        ))}
      </div>
      <div className="custom-row">
        <input
          className="pb-input"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              addCustom();
            }
          }}
          placeholder="Thêm tag khác…"
        />
        <button className="btn" onClick={addCustom} disabled={!custom.trim()}>
          +
        </button>
      </div>
    </div>
  );
}
