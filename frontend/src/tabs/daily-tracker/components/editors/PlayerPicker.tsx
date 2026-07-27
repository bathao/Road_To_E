import { useEffect, useRef, useState } from "react";
import type { Player } from "../../types";
import { trackerApi } from "../../api";
import { rankOf } from "../../../../shared/rank";

// Points + real rank ("1550 · D") — replaced the retired relative label
// chips (Trên/Ngang/Dưới) on 2026-07-27.
function PointsChip({ p }: { p: Player }) {
  if (p.points == null) {
    return <span className="level-chip level-unrated">chưa xếp</span>;
  }
  return (
    <span className="level-chip level-points">
      {p.points} · {rankOf(p.points)}
    </span>
  );
}

// A combobox to pick a player from the shared pool, or add a new one inline
// (name + points; the legacy relative label is derived server-side). New
// players land in the Database tab automatically — same table.
// Returns the selected Player (or null when cleared).
export default function PlayerPicker({
  label,
  value,
  onChange,
  pipsEditable = false,
}: {
  label: string;
  value: Player | null;
  onChange: (p: Player | null) => void;
  // When true (opponent pickers), the selected pill shows a "đánh gai" toggle
  // and the add-new form a "đánh gai" checkbox. Off for the partner picker.
  pipsEditable?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Player[]>([]);
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newPoints, setNewPoints] = useState(""); // empty = unrated (fill in later)
  const [newPips, setNewPips] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const closeTimer = useRef<number | undefined>(undefined);

  // Debounced search whenever the dropdown is open. `alive` drops responses
  // that land after the query changed (out-of-order results).
  useEffect(() => {
    if (!open) return;
    let alive = true;
    const t = setTimeout(async () => {
      try {
        const r = await trackerApi.searchPlayers(query.trim());
        if (alive) setResults(r);
      } catch {
        if (alive) setResults([]);
      }
    }, 180);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [query, open]);

  const select = (p: Player) => {
    onChange(p);
    setOpen(false);
    setAdding(false);
    setQuery("");
    setNewPoints("");
    setNewPips(false);
  };

  const parsedPoints = newPoints.trim() === "" ? null : Number(newPoints);
  const pointsValid =
    parsedPoints === null ||
    (!Number.isNaN(parsedPoints) && parsedPoints >= 0 && parsedPoints <= 3000);

  const addNew = async () => {
    const name = query.trim();
    if (!name || busy || !pointsValid) return;
    setBusy(true);
    try {
      const p = await trackerApi.createPlayer({
        name,
        plays_pips: newPips,
        points: parsedPoints,
      });
      setError(null);
      select(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  // Flip the selected opponent's "đánh gai" flag (persisted on the player, so it
  // applies to every match against them) and reflect it back up.
  const togglePips = async () => {
    if (!value || busy) return;
    setBusy(true);
    try {
      const updated = await trackerApi.updatePlayer(value.id, {
        name: value.name,
        level: value.level,
        note: value.note,
        plays_pips: !value.plays_pips,
      });
      setError(null);
      onChange(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  // Selected state: a pill with the name + level, plus a change/clear button.
  if (value) {
    return (
      <div className="player-row">
        <span className="seg-label">{label}</span>
        <div className="player-selected">
          <span className="player-name">{value.name}</span>
          <PointsChip p={value} />
          {value.plays_pips && (
            <span className="pips-chip" title="Đối thủ đánh gai">
              🏓 Gai
            </span>
          )}
          {pipsEditable && (
            <button
              className={`pips-toggle${value.plays_pips ? " active" : ""}`}
              title={
                value.plays_pips
                  ? "Bỏ đánh dấu đánh gai"
                  : "Đánh dấu: đối thủ đánh gai"
              }
              onClick={togglePips}
              disabled={busy}
            >
              {value.plays_pips ? "✓ Gai" : "Gai?"}
            </button>
          )}
          <button
            className="icon-btn"
            title="Đổi người"
            onClick={() => onChange(null)}
          >
            ✕
          </button>
        </div>
        {error && <div className="pb-error">⚠ {error}</div>}
      </div>
    );
  }

  const exactExists = results.some(
    (r) => r.name.toLowerCase() === query.trim().toLowerCase()
  );

  return (
    <div className="player-row">
      <span className="seg-label">{label}</span>
      <div
        className="player-combo"
        onBlur={() => {
          closeTimer.current = window.setTimeout(() => setOpen(false), 150);
        }}
        onFocus={() => {
          window.clearTimeout(closeTimer.current);
          setOpen(true);
        }}
      >
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            // Typing = searching. After a pick the input may still hold
            // focus (mousedown is prevented), so onFocus won't re-fire —
            // without this the dropdown stays closed while typing (seen in
            // the tournament team picker, which keeps the combo mounted).
            setOpen(true);
          }}
          placeholder="Tìm hoặc thêm người…"
        />
        {open && (
          <div className="player-dropdown">
            {results.map((p) => (
              <button
                key={p.id}
                className="player-option"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => select(p)}
              >
                <span className="player-name">{p.name}</span>
                <PointsChip p={p} />
                {p.plays_pips && (
                  <span className="pips-chip" title="Đối thủ đánh gai">
                    🏓 Gai
                  </span>
                )}
              </button>
            ))}
            {results.length === 0 && !query.trim() && (
              <div className="player-hint">Gõ tên để tìm…</div>
            )}

            {query.trim() && !exactExists && (
              <div
                className="player-add"
                onMouseDown={(e) => {
                  // Keep the search input focused when clicking buttons (so
                  // the dropdown stays open), but let real form controls take
                  // focus — a blanket preventDefault made the points input
                  // unfocusable (couldn't type a new player's points). Focus
                  // moving INSIDE the combo keeps it open anyway (the
                  // container's onFocus clears the close timer).
                  if ((e.target as HTMLElement).tagName !== "INPUT") {
                    e.preventDefault();
                  }
                }}
              >
                {!adding ? (
                  <button className="player-add-btn" onClick={() => setAdding(true)}>
                    + Thêm “{query.trim()}”
                  </button>
                ) : (
                  <div className="player-add-form">
                    <div className="player-add-name">
                      Thêm <b>{query.trim()}</b> — điểm:
                    </div>
                    <div className="player-add-points">
                      <input
                        type="number"
                        min={0}
                        max={3000}
                        placeholder="chưa rõ"
                        value={newPoints}
                        onChange={(e) => setNewPoints(e.target.value)}
                      />
                      {pointsValid && parsedPoints !== null && (
                        <span className="db-rank">{rankOf(parsedPoints)}</span>
                      )}
                      {!pointsValid && (
                        <span className="pb-error">0–3000</span>
                      )}
                    </div>
                    {pipsEditable && (
                      <label className="pips-check">
                        <input
                          type="checkbox"
                          checked={newPips}
                          onChange={(e) => setNewPips(e.target.checked)}
                        />
                        🏓 Đối thủ đánh gai
                      </label>
                    )}
                    <button
                      className="btn primary"
                      onClick={addNew}
                      disabled={busy || !pointsValid}
                    >
                      Lưu người mới
                    </button>
                    {error && <div className="pb-error">⚠ {error}</div>}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
