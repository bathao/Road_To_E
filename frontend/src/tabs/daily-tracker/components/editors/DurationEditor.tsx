import { useEffect, useState } from "react";
import type { Activity, Category, Coach } from "../../types";
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
// Train-with-Coach cells additionally pick WHICH coach the session was with
// (user 2026-08-15): the package coach is the preselected norm; per-session
// coaches (Phi Vũ) never consume the 10-session block, so the ★ hides for
// them. New coaches are added inline.
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
  onSave: (
    minutes: number,
    note: string,
    isPackageStart: boolean,
    coachId: number | null
  ) => void;
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

  // Coach picker (coach cells only). Stored coach wins; otherwise the first
  // package coach (the seeded default) once the roster loads.
  const [coaches, setCoaches] = useState<Coach[]>([]);
  const [coachId, setCoachId] = useState<number | null>(
    current?.coach_id ?? null
  );
  const [addingCoach, setAddingCoach] = useState(false);
  const [newCoachName, setNewCoachName] = useState("");
  const [newCoachPackage, setNewCoachPackage] = useState(false);
  const [coachError, setCoachError] = useState<string | null>(null);
  useEffect(() => {
    if (!isCoach) return;
    let alive = true;
    trackerApi
      .getCoaches()
      .then((list) => {
        if (!alive) return;
        setCoaches(list);
        setCoachId(
          (cur) => cur ?? list.find((c) => c.counts_package)?.id ?? null
        );
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [isCoach]);
  const selectedCoach = coaches.find((c) => c.id === coachId);
  // A per-session coach's ★ is a package-math no-op — don't offer it (and
  // drop a leftover tick when switching to such a coach).
  const perSession = selectedCoach ? !selectedCoach.counts_package : false;
  const starValue = packageStart && !perSession;

  const addCoach = async () => {
    const name = newCoachName.trim();
    if (!name) return;
    try {
      const c = await trackerApi.createCoach(name, newCoachPackage);
      setCoaches((list) => [...list, c]);
      setCoachId(c.id);
      setAddingCoach(false);
      setNewCoachName("");
      setNewCoachPackage(false);
      setCoachError(null);
    } catch (e) {
      setCoachError(e instanceof Error ? e.message : String(e));
    }
  };

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

      {isCoach && (
        <div className="seg-row">
          <span className="seg-label">Coach</span>
          <div className="seg">
            {coaches.map((c) => (
              <button
                key={c.id}
                className={`seg-btn${coachId === c.id ? " active" : ""}`}
                title={
                  c.counts_package
                    ? "Sessions count toward the 10-session package"
                    : "Paid per session — not on the package"
                }
                onClick={() => setCoachId(c.id)}
              >
                {c.name}
              </button>
            ))}
            <button
              className={`seg-btn${addingCoach ? " active" : ""}`}
              title="Add a new coach"
              onClick={() => setAddingCoach((v) => !v)}
            >
              ＋
            </button>
          </div>
        </div>
      )}
      {isCoach && addingCoach && (
        <div className="coach-add-row">
          <input
            type="text"
            className="pb-input"
            placeholder="New coach's name"
            value={newCoachName}
            onChange={(e) => setNewCoachName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void addCoach();
            }}
          />
          <label className="coach-add-pkg">
            <input
              type="checkbox"
              checked={newCoachPackage}
              onChange={(e) => setNewCoachPackage(e.target.checked)}
            />
            <span>Sells 10-session packages</span>
          </label>
          <button
            className="btn"
            disabled={newCoachName.trim() === ""}
            onClick={() => void addCoach()}
          >
            Add
          </button>
        </div>
      )}
      {coachError && (
        <div className="error-banner" onClick={() => setCoachError(null)}>
          ⚠ {coachError}
        </div>
      )}

      <div className="chip-row">
        {CHIPS.map((c) => (
          <button
            key={c.minutes}
            className={`chip${currentMinutes === c.minutes ? " active" : ""}`}
            onClick={() => onSave(c.minutes, note, starValue, coachId)}
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
          // A blank/invalid number would save 0 minutes, which the backend
          // treats as "delete the entry" — require a real number instead
          // (the explicit "Clear entry" button below handles deletion).
          disabled={custom.trim() === "" || Number.isNaN(Number(custom))}
          onClick={() => onSave(Number(custom) || 0, note, starValue, coachId)}
        >
          Save
        </button>
      </div>

      {isCoach && !perSession && (
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
