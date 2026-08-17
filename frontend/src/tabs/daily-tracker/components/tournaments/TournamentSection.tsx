// Bottom-of-page tournament manager: UPCOMING cards with countdown + a
// collapsed add/edit form. Deliberately NOT a results store — match results
// live in the grid above; a tournament here is only "on day X I play
// discipline Y" so the Head Coach can plan. Played tournaments left this
// section 2026-08-01 (user request): entering results retires the card, and
// the history lives in the Profile tab's Tournament Record (read-only —
// editing/deleting a played tournament has no GUI path anymore).
import { useState } from "react";
import type {
  Player,
  Tournament,
  TournamentDiscipline,
  TournamentEntryIn,
  TournamentIn,
  TournamentsResponse,
} from "../../types";
import { tournamentApi } from "../../api";
import { useMutate } from "../../../../shared/useApi";
import { prettyDate } from "../../../../shared/dates";
import PlayerPicker from "../editors/PlayerPicker";
import { countdownText, daysUntil, entryLabel, isPast } from "./helpers";

// The fixed rank ladder (A strongest → I weakest). A tournament's limit is a
// set of these; "Open" means explicitly unrestricted.
const RANKS = ["A", "B", "C", "D", "E", "F", "G", "H", "I"] as const;
const OPEN = "Open";

// One entry row while editing (partner kept as {id, name} — enough for the
// payload and the pill; PlayerPicker supplies a full Player on change).
interface EntryDraft {
  // Stable React key for the row. Rows are removable — index keys would
  // hand row i+1's PlayerPicker state (half-typed search, add-form) to row
  // i after a deletion. Existing entries key by id; new rows get a counter.
  key: string;
  id: number | null; // existing entry's id (null = new) — keeps match links
  discipline: TournamentDiscipline;
  partner: { id: number; name: string } | null;
  teammates: { id: number; name: string }[]; // team roster from the pool
  team_members: string; // optional team name / note
}

let nextDraftKey = 0;
const newEntryDraft = (): EntryDraft => ({
  key: `new-${nextDraftKey++}`,
  id: null,
  discipline: "singles",
  partner: null,
  teammates: [],
  team_members: "",
});

interface Draft {
  name: string;
  location: string;
  start_date: string;
  end_date: string;
  // Rank limit: selected ranks, or explicit Open, or neither (unspecified).
  levels: string[];
  open: boolean;
  // Points-capped tournaments ("giải 1300 điểm"): max points allowed, as
  // typed ("" = no cap). Kept separate from the rank letters on purpose.
  points: string;
  note: string;
  entries: EntryDraft[];
}

const EMPTY_DRAFT: Draft = {
  name: "",
  location: "",
  start_date: "",
  end_date: "",
  levels: [],
  open: false,
  points: "",
  note: "",
  entries: [newEntryDraft()],
};

// One-tap presets for the common points caps; any other value types fine.
const POINTS_PRESETS = [1100, 1200, 1300];

function toDraft(t: Tournament): Draft {
  const raw = (t.level_limit ?? "").trim();
  const open = raw.toLowerCase() === OPEN.toLowerCase();
  return {
    name: t.name,
    location: t.location ?? "",
    start_date: t.start_date,
    end_date: t.end_date ?? "",
    levels: open ? [] : raw.split(/\s+/).filter((r) => RANKS.includes(r as never)),
    open,
    points: t.points_limit ? String(t.points_limit) : "",
    note: t.note ?? "",
    entries: t.entries.map((e) => ({
      key: `e${e.id}`,
      id: e.id,
      discipline: e.discipline,
      partner:
        e.partner_id && e.partner_name
          ? { id: e.partner_id, name: e.partner_name }
          : null,
      teammates: (e.teammate_ids ?? []).map((id, i) => ({
        id,
        name: (e.teammate_names ?? [])[i] ?? "?",
      })),
      team_members: e.team_members ?? "",
    })),
  };
}

function toPayload(d: Draft): TournamentIn {
  const entries: TournamentEntryIn[] = d.entries.map((e) => ({
    id: e.id,
    discipline: e.discipline,
    partner_id: e.discipline === "doubles" ? e.partner?.id ?? null : null,
    teammate_ids: e.discipline === "team" ? e.teammates.map((p) => p.id) : [],
    team_members: e.discipline === "team" ? e.team_members.trim() || null : null,
  }));
  // Normalize A→I regardless of click order; Open wins over any selection.
  const levels = RANKS.filter((r) => d.levels.includes(r)).join(" ");
  const points = Number(d.points);
  return {
    name: d.name.trim(),
    location: d.location.trim() || null,
    start_date: d.start_date,
    end_date: d.end_date || null,
    level_limit: d.open ? OPEN : levels || null,
    // Open = no limit at all — it clears the points cap too.
    points_limit: !d.open && Number.isInteger(points) && points > 0 ? points : null,
    note: d.note.trim() || null,
    entries,
  };
}

const DISCIPLINES: { key: TournamentDiscipline; label: string }[] = [
  { key: "singles", label: "Singles" },
  { key: "doubles", label: "Doubles" },
  { key: "team", label: "Team" },
];

function EntryRow({
  entry,
  onChange,
  onRemove,
}: {
  entry: EntryDraft;
  onChange: (e: EntryDraft) => void;
  onRemove: () => void;
}) {
  return (
    <div className="tour-entry-row">
      <div className="seg">
        {DISCIPLINES.map((d) => (
          <button
            key={d.key}
            className={`seg-btn${entry.discipline === d.key ? " active" : ""}`}
            onClick={() => onChange({ ...entry, discipline: d.key })}
          >
            {d.label}
          </button>
        ))}
      </div>
      {entry.discipline === "doubles" &&
        (entry.partner ? (
          <div className="tour-partner">
            👥 {entry.partner.name}
            <button
              className="icon-btn"
              title="Change doubles partner"
              onClick={() => onChange({ ...entry, partner: null })}
            >
              ✕
            </button>
          </div>
        ) : (
          <PlayerPicker
            label="Partner with"
            value={null}
            onChange={(p: Player | null) =>
              onChange({ ...entry, partner: p ? { id: p.id, name: p.name } : null })
            }
          />
        ))}
      {entry.discipline === "team" && (
        <div className="tour-team">
          {entry.teammates.map((p) => (
            <span key={p.id} className="tour-partner">
              👥 {p.name}
              <button
                className="icon-btn"
                title="Remove from team"
                onClick={() =>
                  onChange({
                    ...entry,
                    teammates: entry.teammates.filter((x) => x.id !== p.id),
                  })
                }
              >
                ✕
              </button>
            </span>
          ))}
          <PlayerPicker
            label="Teammate"
            value={null}
            onChange={(p: Player | null) => {
              if (p && !entry.teammates.some((x) => x.id === p.id)) {
                onChange({
                  ...entry,
                  teammates: [...entry.teammates, { id: p.id, name: p.name }],
                });
              }
            }}
          />
          <input
            type="text"
            className="pb-input"
            placeholder="Team name (optional, e.g. CLB X)"
            value={entry.team_members}
            onChange={(e) => onChange({ ...entry, team_members: e.target.value })}
          />
        </div>
      )}
      <button className="icon-btn" title="Remove this event" onClick={onRemove}>
        🗑
      </button>
    </div>
  );
}

function TournamentForm({
  initial,
  busy,
  onSave,
  onCancel,
}: {
  initial: Draft;
  busy: boolean;
  onSave: (d: Draft) => void;
  onCancel: () => void;
}) {
  const [d, setD] = useState<Draft>(initial);
  const valid = d.name.trim() !== "" && d.start_date !== "" && d.entries.length > 0;
  const setEntry = (i: number, e: EntryDraft) =>
    setD({ ...d, entries: d.entries.map((x, j) => (j === i ? e : x)) });

  return (
    <div className="tour-form">
      <div className="tour-form-row">
        <input
          type="text"
          className="pb-input tour-name"
          placeholder="Tournament name *"
          value={d.name}
          onChange={(e) => setD({ ...d, name: e.target.value })}
        />
        <input
          type="text"
          className="pb-input"
          placeholder="Location"
          value={d.location}
          onChange={(e) => setD({ ...d, location: e.target.value })}
        />
      </div>
      <div className="tour-form-row">
        <label>
          Start date *
          <input
            type="date"
            className="pb-input"
            value={d.start_date}
            onChange={(e) => setD({ ...d, start_date: e.target.value })}
          />
        </label>
        <label>
          End date (if multi-day)
          <input
            type="date"
            className="pb-input"
            value={d.end_date}
            min={d.start_date}
            onChange={(e) => setD({ ...d, end_date: e.target.value })}
          />
        </label>
      </div>

      <div>
        <div className="tour-entries-head">
          Tournament level limit (click the ranks allowed to play):
        </div>
        <div className="seg tour-levels">
          <button
            className={`seg-btn${d.open ? " active" : ""}`}
            title="Open tournament — no limit at all (clears ranks and points)"
            onClick={() => setD({ ...d, open: !d.open, levels: [], points: "" })}
          >
            {OPEN}
          </button>
          {RANKS.map((r) => (
            <button
              key={r}
              className={`seg-btn${d.levels.includes(r) ? " active" : ""}`}
              onClick={() =>
                setD({
                  ...d,
                  open: false,
                  levels: d.levels.includes(r)
                    ? d.levels.filter((x) => x !== r)
                    : [...d.levels, r],
                })
              }
            >
              {r}
            </button>
          ))}
        </div>
        <div className="tour-entries-head">
          Points limit (for points-capped tournaments, e.g. "giải 1300"; Open
          = no cap, anyone can play):
        </div>
        <div className="tour-points-row">
          <div className="seg">
            <button
              className={`seg-btn${d.open ? " active" : ""}`}
              title="Open class — no points cap, anyone can play"
              onClick={() => setD({ ...d, open: !d.open, levels: [], points: "" })}
            >
              {OPEN}
            </button>
            {POINTS_PRESETS.map((p) => (
              <button
                key={p}
                className={`seg-btn${d.points === String(p) ? " active" : ""}`}
                onClick={() =>
                  setD({
                    ...d,
                    open: false,
                    points: d.points === String(p) ? "" : String(p),
                  })
                }
              >
                {p}
              </button>
            ))}
          </div>
          <input
            type="number"
            className="pb-input tour-points-input"
            placeholder="Other…"
            min={1}
            step={50}
            value={d.points}
            onChange={(e) => setD({ ...d, open: false, points: e.target.value })}
          />
        </div>
      </div>

      <div className="tour-entries">
        <div className="tour-entries-head">Registered events:</div>
        {d.entries.map((e, i) => (
          <EntryRow
            key={e.key}
            entry={e}
            onChange={(x) => setEntry(i, x)}
            onRemove={() =>
              setD({ ...d, entries: d.entries.filter((_, j) => j !== i) })
            }
          />
        ))}
        <button
          className="btn"
          onClick={() =>
            setD({ ...d, entries: [...d.entries, newEntryDraft()] })
          }
        >
          ＋ Add event
        </button>
      </div>

      <input
        type="text"
        className="pb-input"
        placeholder="Notes (fees, schedule, links…)"
        value={d.note}
        onChange={(e) => setD({ ...d, note: e.target.value })}
      />

      <div className="tour-form-actions">
        <button className="btn primary" disabled={!valid || busy} onClick={() => onSave(d)}>
          Save tournament
        </button>
        <button className="btn" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}

function TournamentCard({
  t,
  onEdit,
  onDelete,
  onEliminate,
}: {
  t: Tournament;
  onEdit: () => void;
  onDelete: () => void;
  // Knocked-out toggle (the ☠ chip un-marks; marking happens in the match
  // editor's tournament banner).
  onEliminate: (entryId: number, eliminated: boolean) => void;
}) {
  // Only upcoming cards render here — entering results (or marking every
  // entry knocked out) retires a card to the Profile Tournament Record, so
  // result/warning chips never apply and at least one entry is alive.
  const urgent = daysUntil(t) <= 7;
  return (
    <div className={`tour-card${urgent ? " urgent" : ""}`}>
      <div className="tour-card-head">
        <span className="tour-card-name">🏆 {t.name}</span>
        <span className="tour-card-count">{countdownText(t)}</span>
      </div>
      <div className="tour-card-meta">
        {prettyDate(t.start_date)}
        {t.end_date ? ` → ${prettyDate(t.end_date)}` : ""}
        {t.location ? ` · ${t.location}` : ""}
      </div>
      <div className="tour-card-chips">
        {t.level_limit && (
          <span className="tour-chip tour-chip-limit">Level: {t.level_limit}</span>
        )}
        {!!t.points_limit && (
          <span className="tour-chip tour-chip-limit">≤ {t.points_limit} pts</span>
        )}
        {t.entries.map((e) =>
          e.eliminated ? (
            <button
              key={e.id}
              className="tour-chip tour-chip-out"
              title="Knocked out — no more matches collected for this event. Click to un-mark."
              onClick={() => onEliminate(e.id, false)}
            >
              ☠ {entryLabel(e)} — out
            </button>
          ) : (
            <span key={e.id} className="tour-chip">
              {entryLabel(e)}
            </span>
          )
        )}
      </div>
      {t.note && <div className="tour-card-note">📝 {t.note}</div>}
      <div className="tour-card-actions">
        <button className="btn" onClick={onEdit}>
          Edit
        </button>
        <button
          className="btn"
          onClick={() => {
            if (window.confirm(`Delete tournament "${t.name}"?`)) onDelete();
          }}
        >
          Delete
        </button>
      </div>
    </div>
  );
}

export default function TournamentSection({
  tournaments,
  onData,
}: {
  tournaments: Tournament[];
  // Mutations return the fresh list; the parent owns the state (the strip
  // reads the same data).
  onData: (r: TournamentsResponse) => void;
}) {
  const { run, error, busy, clearError } = useMutate();
  // null = form closed; "new" = adding; a Tournament = editing it.
  const [editing, setEditing] = useState<Tournament | "new" | null>(null);

  const upcoming = tournaments.filter((t) => !isPast(t));

  const save = async (d: Draft) => {
    const payload = toPayload(d);
    const out = await run(() =>
      editing !== null && editing !== "new"
        ? tournamentApi.update(editing.id, payload)
        : tournamentApi.create(payload)
    );
    if (out === undefined) return; // failed → keep the form open
    onData(out);
    setEditing(null);
  };

  const remove = async (id: number) => {
    const out = await run(() => tournamentApi.remove(id));
    if (out !== undefined) onData(out);
  };

  const setEliminated = async (entryId: number, eliminated: boolean) => {
    const out = await run(() => tournamentApi.setEliminated(entryId, eliminated));
    if (out !== undefined) onData(out);
  };

  return (
    <section className="tour-section">
      <div className="tour-head">
        <h2>🏆 Tournaments</h2>
        {editing === null && (
          <button className="btn primary" onClick={() => setEditing("new")}>
            ＋ Add tournament
          </button>
        )}
      </div>
      <p className="tour-hint">
        Pin your tournament schedule so the coach can plan training. Match
        results still go into the grid as usual.
      </p>

      {error && (
        <div className="error-banner" onClick={clearError}>
          ⚠ {error}
        </div>
      )}

      {editing !== null && (
        <TournamentForm
          // Remount per target: the form seeds its draft from `initial` via
          // useState, and the cards' Edit buttons stay clickable while it's
          // open — without the key, switching targets kept the PREVIOUS
          // draft and save() wrote it over the newly picked tournament.
          key={editing === "new" ? "new" : editing.id}
          initial={editing === "new" ? EMPTY_DRAFT : toDraft(editing)}
          busy={busy}
          onSave={save}
          onCancel={() => setEditing(null)}
        />
      )}

      {upcoming.length === 0 && editing === null && (
        <div className="tour-empty">
          No upcoming tournaments — click <b>＋ Add tournament</b> once your
          schedule is set.
        </div>
      )}
      <div className="tour-cards">
        {upcoming.map((t) => (
          <TournamentCard
            key={t.id}
            t={t}
            onEdit={() => setEditing(t)}
            onDelete={() => remove(t.id)}
            onEliminate={setEliminated}
          />
        ))}
      </div>
    </section>
  );
}
