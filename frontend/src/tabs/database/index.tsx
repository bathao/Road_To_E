// Database tab: every player in the pool, with hand-maintained BBTV points.
// Points are STATIC anchors; rank (G/F/E…) derives from points. The user's
// own DYNAMIC rating lives on the Profile tab (moved 2026-07-27) — this tab
// is other people only. The legacy relative labels (below/equal/above) live
// only in the DB now — hidden from this tab, superseded by points.
import { useMemo, useRef, useState } from "react";
import { useLoad, useMutate } from "../../shared/useApi";
import { rankOf } from "../../shared/rank";
import { databaseApi } from "./api";
import PlayerMatchesModal from "./PlayerMatchesModal";
import type { RoleFilter } from "./PlayerMatchesModal";
import type { PlayerDbRow, PlayersDbResponse } from "./types";

function RankChip({ points }: { points: number | null }) {
  const rank = rankOf(points);
  if (!rank) return <span className="db-rank db-rank-none">unranked</span>;
  return <span className={`db-rank db-rank-${rank}`}>{rank}</span>;
}

// One row: points edited locally, saved on blur/Enter (only when changed).
// Save feedback: ✓ fades out on success, red input border on failure.
function PlayerRow({
  p,
  busy,
  onSave,
  onRename,
  onOpenMatches,
}: {
  p: PlayerDbRow;
  busy: boolean;
  onSave: (p: PlayerDbRow, points: number | null, playsPips: boolean) => Promise<boolean>;
  onRename: (p: PlayerDbRow, name: string) => Promise<boolean>;
  onOpenMatches: (p: PlayerDbRow, role: RoleFilter) => void;
}) {
  const [draft, setDraft] = useState(p.points === null ? "" : String(p.points));
  const [flash, setFlash] = useState<"saved" | "failed" | null>(null);
  const flashTimer = useRef<number | undefined>(undefined);
  // null = not editing the name; Escape cancels via skipBlurSave so the
  // input's blur (fired by the state change) doesn't save anyway.
  const [nameDraft, setNameDraft] = useState<string | null>(null);
  const skipBlurSave = useRef(false);
  const parsed = draft.trim() === "" ? null : Number(draft);
  const dirty = parsed !== p.points;
  const valid = parsed === null || (!Number.isNaN(parsed) && parsed >= 0 && parsed <= 3000);

  const doSave = async (points: number | null, playsPips: boolean) => {
    const ok = await onSave(p, points, playsPips);
    window.clearTimeout(flashTimer.current);
    setFlash(ok ? "saved" : "failed");
    if (ok) flashTimer.current = window.setTimeout(() => setFlash(null), 1500);
  };

  const save = () => {
    if (!dirty || !valid || parsed === null) return; // clearing isn't supported
    void doSave(parsed, p.plays_pips);
  };

  const saveName = async () => {
    if (skipBlurSave.current) {
      skipBlurSave.current = false;
      return;
    }
    const name = (nameDraft ?? "").trim();
    if (!name || name === p.name) {
      setNameDraft(null); // nothing to do — just close the editor
      return;
    }
    const ok = await onRename(p, name);
    window.clearTimeout(flashTimer.current);
    setFlash(ok ? "saved" : "failed");
    if (ok) {
      setNameDraft(null);
      flashTimer.current = window.setTimeout(() => setFlash(null), 1500);
    }
    // On failure (e.g. the name already exists) the editor stays open with
    // the draft so the user can adjust; the error banner explains why.
  };

  return (
    <tr className={p.points === null ? "db-row-unrated" : ""}>
      <td className="db-name">
        {nameDraft === null ? (
          <>
            {p.name}
            <button
              className="db-name-edit"
              title="Rename this player — every match in the history follows automatically"
              disabled={busy}
              onClick={() => setNameDraft(p.name)}
            >
              ✏️
            </button>
          </>
        ) : (
          <input
            type="text"
            className={`db-name-input${flash === "failed" ? " db-input-failed" : ""}`}
            autoFocus
            value={nameDraft}
            onChange={(e) => {
              setNameDraft(e.target.value);
              if (flash === "failed") setFlash(null);
            }}
            onBlur={() => void saveName()}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              if (e.key === "Escape") {
                skipBlurSave.current = true;
                setNameDraft(null);
                setFlash(null);
              }
            }}
          />
        )}
      </td>
      <td className="db-points">
        <input
          type="number"
          min={0}
          max={3000}
          placeholder="—"
          className={flash === "failed" ? "db-input-failed" : undefined}
          value={draft}
          onChange={(e) => {
            setDraft(e.target.value);
            if (flash === "failed") setFlash(null);
          }}
          onBlur={save}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
        />
        {dirty && valid && parsed !== null && (
          <span className="db-dirty" title="Not saved — leave the field or press Enter to save">
            ●
          </span>
        )}
        {flash === "saved" && !dirty && (
          <span className="db-saved" title="Saved">
            ✓
          </span>
        )}
        {flash === "failed" && (
          <span className="db-failed" title="Save failed — retry">
            ✕
          </span>
        )}
      </td>
      <td>
        <RankChip points={p.points} />
      </td>
      <td className="db-pips">
        <label>
          <input
            type="checkbox"
            checked={p.plays_pips}
            disabled={busy}
            onChange={(e) => void doSave(p.points, e.target.checked)}
          />
          🏓 pips
        </label>
      </td>
      <td className="db-count">
        {p.matches_vs ? (
          <button
            className="db-count-btn"
            title={`See all ${p.matches_vs} matches vs ${p.name}`}
            onClick={() => onOpenMatches(p, "vs")}
          >
            {p.matches_vs}
          </button>
        ) : (
          "—"
        )}
      </td>
      <td className="db-count">
        {p.matches_with ? (
          <button
            className="db-count-btn"
            title={`See all ${p.matches_with} matches with ${p.name} as my partner`}
            onClick={() => onOpenMatches(p, "with")}
          >
            {p.matches_with}
          </button>
        ) : (
          "—"
        )}
      </td>
    </tr>
  );
}

// Sortable columns + each one's most useful FIRST direction (second click
// reverses): names read A→Z, points/counts read biggest-first.
type SortKey = "name" | "points" | "vs" | "with";
const SORT_DEFAULT_DIR: Record<SortKey, 1 | -1> = {
  name: 1,
  points: -1,
  vs: -1,
  with: -1,
};

// Header cell: click to sort by this column, click again to reverse.
// The active column shows ▲/▼; inactive ones a faint ↕ hint.
function SortableTh({
  label,
  k,
  sort,
  onSort,
  title,
}: {
  label: string;
  k: SortKey;
  sort: { key: SortKey; dir: 1 | -1 } | null;
  onSort: (k: SortKey) => void;
  title?: string;
}) {
  const active = sort?.key === k;
  return (
    <th
      className={`db-th-sort${active ? " active" : ""}`}
      title={title}
      onClick={() => onSort(k)}
    >
      {label}
      <span className="db-sort-arrow">
        {active ? (sort!.dir === 1 ? "▲" : "▼") : "↕"}
      </span>
    </th>
  );
}

export default function DatabaseTab() {
  const { data, setData, reload, error: loadError } = useLoad<PlayersDbResponse>(
    () => databaseApi.list(),
    []
  );
  const { run, error, busy, clearError } = useMutate();
  const [query, setQuery] = useState("");
  // "+ Add player" inline form (backend get-or-creates by name, so re-adding
  // an existing player just returns the existing row — harmless).
  const [addOpen, setAddOpen] = useState(false);
  const [addName, setAddName] = useState("");
  const [addPoints, setAddPoints] = useState("");
  const [addPips, setAddPips] = useState(false);
  // null = the server's default order (rated by points desc, unrated last).
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 } | null>(null);
  // Per-player match drill-down, opened from a count cell with its role.
  const [drill, setDrill] = useState<{ p: PlayerDbRow; role: RoleFilter } | null>(
    null
  );

  const players = data?.players ?? [];
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q
      ? players.filter((p) => p.name.toLowerCase().includes(q))
      : players;
    if (!sort) return list;
    const { key, dir } = sort;
    return [...list].sort((a, b) => {
      if (key === "name") return dir * a.name.localeCompare(b.name, "vi");
      if (key === "vs") return dir * (a.matches_vs - b.matches_vs);
      if (key === "with") return dir * (a.matches_with - b.matches_with);
      // Points: unrated players sink to the bottom in BOTH directions.
      if (a.points === null && b.points === null)
        return a.name.localeCompare(b.name, "vi");
      if (a.points === null) return 1;
      if (b.points === null) return -1;
      return dir * (a.points - b.points);
    });
  }, [players, query, sort]);
  const rated = players.filter((p) => p.points !== null).length;

  const toggleSort = (key: SortKey) =>
    setSort((s) =>
      s?.key === key
        ? { key, dir: -s.dir as 1 | -1 }
        : { key, dir: SORT_DEFAULT_DIR[key] }
    );

  const saveRow = async (
    p: PlayerDbRow,
    points: number | null,
    playsPips: boolean
  ): Promise<boolean> => {
    const out = await run(() =>
      databaseApi.updatePlayer(p.id, {
        name: p.name,
        level: p.level,
        note: p.note ?? null,
        plays_pips: playsPips,
        points,
      })
    );
    if (out === undefined || !data) return false;
    // Patch locally — no full reload, the list keeps its scroll position.
    setData({
      players: data.players.map((x) =>
        x.id === p.id ? { ...x, points, plays_pips: playsPips } : x
      ),
    });
    return true;
  };

  const addPointsParsed = addPoints.trim() === "" ? null : Number(addPoints);
  const addValid =
    addName.trim() !== "" &&
    (addPointsParsed === null ||
      (!Number.isNaN(addPointsParsed) &&
        addPointsParsed >= 0 &&
        addPointsParsed <= 3000));

  const addPlayer = async () => {
    if (!addValid) return;
    const out = await run(() =>
      databaseApi.createPlayer({
        name: addName.trim(),
        plays_pips: addPips,
        points: addPointsParsed,
      })
    );
    if (out === undefined) return; // error banner explains
    setAddOpen(false);
    setAddName("");
    setAddPoints("");
    setAddPips(false);
    reload(); // counts + ordering come from the server — refetch the list
  };

  // Rename: matches store player IDs, so the whole history (grid, h2h,
  // coach) shows the new name on its next load — nothing else to update.
  const renameRow = async (p: PlayerDbRow, name: string): Promise<boolean> => {
    const out = await run(() =>
      databaseApi.updatePlayer(p.id, {
        name,
        level: p.level,
        note: p.note ?? null,
        plays_pips: p.plays_pips,
        points: p.points,
      })
    );
    if (out === undefined || !data) return false;
    setData({
      players: data.players.map((x) => (x.id === p.id ? { ...x, name } : x)),
    });
    return true;
  };

  return (
    <div className="db-tab">
      <div className="db-head">
        <div>
          <h2>🗄️ Player Database</h2>
          <p className="db-sub">
            Each player's points — static anchors, updated by hand when they
            move up or down a level. Level (G/F/E…) derives from points. Your
            dynamic ELO lives on the Profile tab.
          </p>
        </div>
      </div>

      {(error || loadError) && (
        <div className="error-banner" onClick={clearError}>
          ⚠ {error ?? loadError}
        </div>
      )}

      <div className="db-toolbar">
        <input
          type="text"
          className="db-search"
          placeholder="Search by name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <span className="db-progress">
          Rated {rated}/{players.length} players
        </span>
        <button
          className={`btn${addOpen ? "" : " primary"}`}
          onClick={() => setAddOpen((v) => !v)}
        >
          {addOpen ? "Cancel" : "＋ Add player"}
        </button>
      </div>

      {addOpen && (
        <div className="db-add-form">
          <input
            type="text"
            className="pb-input db-add-name"
            placeholder="Name"
            autoFocus
            value={addName}
            onChange={(e) => setAddName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void addPlayer();
              if (e.key === "Escape") setAddOpen(false);
            }}
          />
          <input
            type="number"
            min={0}
            max={3000}
            className="pb-input db-add-points"
            placeholder="Points (empty = unrated)"
            value={addPoints}
            onChange={(e) => setAddPoints(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void addPlayer();
              if (e.key === "Escape") setAddOpen(false);
            }}
          />
          <RankChip points={addValid ? addPointsParsed : null} />
          <label className="db-pips">
            <input
              type="checkbox"
              checked={addPips}
              onChange={(e) => setAddPips(e.target.checked)}
            />
            🏓 pips
          </label>
          <button
            className="btn primary"
            disabled={busy || !addValid}
            title={addValid ? undefined : "Enter a name (points 0–3000 or empty)"}
            onClick={() => void addPlayer()}
          >
            Create
          </button>
        </div>
      )}

      <div className="db-table-wrap">
        <table className="db-table">
          <thead>
            <tr>
              <SortableTh label="Name" k="name" sort={sort} onSort={toggleSort} />
              <SortableTh label="Points" k="points" sort={sort} onSort={toggleSort} />
              <th>Level</th>
              <th>Pips</th>
              <SortableTh
                label="⚔️ Vs me"
                k="vs"
                sort={sort}
                onSort={toggleSort}
                title="Matches where they faced me (opponent)"
              />
              <SortableTh
                label="🤝 With me"
                k="with"
                sort={sort}
                onSort={toggleSort}
                title="Matches where they were my partner"
              />
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => (
              <PlayerRow
                key={p.id}
                p={p}
                busy={busy}
                onSave={saveRow}
                onRename={renameRow}
                onOpenMatches={(pl, role) => setDrill({ p: pl, role })}
              />
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="db-empty">No one matches “{query}”.</div>
        )}
      </div>

      {drill && (
        <PlayerMatchesModal
          player={drill.p}
          initialRole={drill.role}
          onClose={() => setDrill(null)}
        />
      )}
    </div>
  );
}
