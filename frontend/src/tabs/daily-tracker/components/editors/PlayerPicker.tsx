import { useEffect, useRef, useState } from "react";
import type { Player } from "../../types";
import { trackerApi } from "../../api";
// Level metadata lives in shared/; re-export so existing siblings keep importing
// LEVELS / levelShort from the picker.
import { LEVELS, levelShort } from "../../../../shared/levels";
import type { PlayerLevel } from "../../../../shared/levels";
export { LEVELS, levelShort };

// A combobox to pick a player from the shared pool, or add a new one inline
// (name + relative level). Returns the selected Player (or null when cleared).
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
  const [newLevel, setNewLevel] = useState<PlayerLevel>("equal");
  const [newPips, setNewPips] = useState(false);
  const [busy, setBusy] = useState(false);
  const closeTimer = useRef<number | undefined>(undefined);

  // Debounced search whenever the dropdown is open.
  useEffect(() => {
    if (!open) return;
    const t = setTimeout(async () => {
      try {
        setResults(await trackerApi.searchPlayers(query.trim()));
      } catch {
        setResults([]);
      }
    }, 180);
    return () => clearTimeout(t);
  }, [query, open]);

  const select = (p: Player) => {
    onChange(p);
    setOpen(false);
    setAdding(false);
    setQuery("");
    setNewPips(false);
  };

  const addNew = async () => {
    const name = query.trim();
    if (!name || busy) return;
    setBusy(true);
    try {
      const p = await trackerApi.createPlayer({
        name,
        level: newLevel,
        plays_pips: newPips,
      });
      select(p);
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
      onChange(updated);
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
          <span className={`level-chip level-${value.level}`}>
            {levelShort(value.level)}
          </span>
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
          onChange={(e) => setQuery(e.target.value)}
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
                <span className={`level-chip level-${p.level}`}>
                  {levelShort(p.level)}
                </span>
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
              <div className="player-add" onMouseDown={(e) => e.preventDefault()}>
                {!adding ? (
                  <button className="player-add-btn" onClick={() => setAdding(true)}>
                    + Thêm “{query.trim()}”
                  </button>
                ) : (
                  <div className="player-add-form">
                    <div className="player-add-name">
                      Thêm <b>{query.trim()}</b> — trình độ:
                    </div>
                    <div className="seg">
                      {LEVELS.map((l) => (
                        <button
                          key={l.key}
                          className={`seg-btn${newLevel === l.key ? " active" : ""}`}
                          onClick={() => setNewLevel(l.key)}
                        >
                          {l.label}
                        </button>
                      ))}
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
                      disabled={busy}
                    >
                      Lưu người mới
                    </button>
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
