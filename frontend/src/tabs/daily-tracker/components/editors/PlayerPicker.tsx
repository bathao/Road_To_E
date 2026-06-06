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
}: {
  label: string;
  value: Player | null;
  onChange: (p: Player | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Player[]>([]);
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newLevel, setNewLevel] = useState<PlayerLevel>("equal");
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
  };

  const addNew = async () => {
    const name = query.trim();
    if (!name || busy) return;
    setBusy(true);
    try {
      const p = await trackerApi.createPlayer({ name, level: newLevel });
      select(p);
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
