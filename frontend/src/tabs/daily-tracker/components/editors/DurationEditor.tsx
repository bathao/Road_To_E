import { useEffect, useState } from "react";
import type { Activity, Category } from "../../types";
import { trackerApi } from "../../api";

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
  dateIso,
  current,
  onSave,
  onClear,
}: {
  category: Category;
  dateIso: string;
  current: Activity | undefined;
  onSave: (minutes: number, note: string, isPackageStart: boolean) => void;
  onClear: () => void;
}) {
  const [note, setNote] = useState(current?.note ?? "");
  const [custom, setCustom] = useState<string>(
    current ? String(current.duration_minutes) : ""
  );
  const [packageStart, setPackageStart] = useState(
    current?.is_package_start ?? false
  );

  const currentMinutes = current?.duration_minutes ?? 0;
  const isCoach = category.key === "train_with_coach";

  // The package-start box is only usable when this day is a legitimate block
  // boundary (an existing start, or the 11th+ session of the current block).
  // Already-marked starts stay editable so they can be un-marked.
  const [allowed, setAllowed] = useState(current?.is_package_start ?? false);
  useEffect(() => {
    if (!isCoach) return;
    let alive = true;
    trackerApi
      .coachPackageStartAllowed(dateIso)
      .then((r) => {
        if (alive) setAllowed(r.allowed);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [isCoach, dateIso]);

  return (
    <div className="editor">
      <p className="editor-sub">{category.label}</p>

      <div className="chip-row">
        {CHIPS.map((c) => (
          <button
            key={c.minutes}
            className={`chip${currentMinutes === c.minutes ? " active" : ""}`}
            onClick={() => onSave(c.minutes, note, packageStart)}
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
          onClick={() => onSave(Number(custom) || 0, note, packageStart)}
        >
          Save
        </button>
      </div>

      {isCoach && (
        <label className={`package-row${allowed ? "" : " disabled"}`}>
          <input
            type="checkbox"
            checked={packageStart}
            disabled={!allowed}
            onChange={(e) => setPackageStart(e.target.checked)}
          />
          <span>★ Start of a new 10-session package</span>
          {!allowed && (
            <small className="package-hint">
              available on the next package's first session
            </small>
          )}
        </label>
      )}

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
