import { useState } from "react";
import type { Activity, Category } from "../../types";

const CHIPS: { label: string; minutes: number }[] = [
  { label: "15m", minutes: 15 },
  { label: "30m", minutes: 30 },
  { label: "45m", minutes: 45 },
  { label: "1h", minutes: 60 },
  { label: "1h30", minutes: 90 },
  { label: "2h", minutes: 120 },
];

// Fast duration entry: one-tap chips + optional custom value + note.
export default function DurationEditor({
  category,
  current,
  onSave,
  onClear,
}: {
  category: Category;
  current: Activity | undefined;
  onSave: (minutes: number, note: string) => void;
  onClear: () => void;
}) {
  const [note, setNote] = useState(current?.note ?? "");
  const [custom, setCustom] = useState<string>(
    current ? String(current.duration_minutes) : ""
  );

  const currentMinutes = current?.duration_minutes ?? 0;

  return (
    <div className="editor">
      <p className="editor-sub">{category.label}</p>

      <div className="chip-row">
        {CHIPS.map((c) => (
          <button
            key={c.minutes}
            className={`chip${currentMinutes === c.minutes ? " active" : ""}`}
            onClick={() => onSave(c.minutes, note)}
          >
            {c.label}
          </button>
        ))}
      </div>

      <div className="custom-row">
        <label>Custom (minutes)</label>
        <input
          type="number"
          min={0}
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          placeholder="e.g. 75"
        />
        <button
          className="btn primary"
          onClick={() => onSave(Number(custom) || 0, note)}
        >
          Save
        </button>
      </div>

      <div className="note-row">
        <label>Note (optional)</label>
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="optional note"
        />
      </div>

      {current && (
        <button className="btn danger" onClick={onClear}>
          Clear entry
        </button>
      )}
    </div>
  );
}
