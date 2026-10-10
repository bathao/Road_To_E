import { useEffect, useMemo, useRef, useState } from "react";
import { fold } from "../../../shared/fold";
import type { Opponent } from "../types";

// Type-to-search opponent picker for the Tactics tab (replaced the plain
// <select> on 2026-10-10 — 99 opponents sorted by matches played meant a
// player met once sat at the very bottom). Filters the already-loaded list
// client-side, diacritic-insensitive ("vy" → "Nguyễn Phúc Hoàng Vy"); an
// empty query shows the full list in the API's order so browsing still
// works. Nobody can be ADDED here — only people already played in singles
// have a tactics page (the backend builds the list).
function describe(o: Opponent): string {
  const n = o.matches_vs;
  return `${n} ${n === 1 ? "match" : "matches"} (${o.wins}W–${o.losses}L)`;
}

export default function OpponentPicker({
  opponents,
  selected,
  onPick,
}: {
  opponents: Opponent[];
  selected: Opponent | null;
  onPick: (id: number | null) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<number | undefined>(undefined);

  const results = useMemo(() => {
    const q = fold(query.trim());
    if (!q) return opponents;
    return opponents.filter((o) => fold(o.name).includes(q));
  }, [opponents, query]);

  // Keep the keyboard cursor inside the (shrinking) result list and the
  // highlighted row in view.
  useEffect(() => {
    setCursor(0);
  }, [query]);
  useEffect(() => {
    const el = listRef.current?.children[cursor] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [cursor, open]);

  const select = (o: Opponent) => {
    onPick(o.id);
    setQuery("");
    setOpen(false);
  };

  const clear = () => {
    onPick(null);
    // Let the pill unmount, then hand focus to the fresh input.
    window.setTimeout(() => inputRef.current?.focus(), 0);
  };

  if (selected) {
    return (
      <div className="tac-pick">
        <button
          className="tac-pick-pill"
          title="Change opponent"
          onClick={clear}
        >
          <span className="player-name">{selected.name}</span>
          <span className="tac-pick-meta">· {describe(selected)}</span>
          {selected.plays_pips && (
            <span className="pips-chip" title="Opponent plays pips">
              🏓 Pips
            </span>
          )}
          <span className="tac-pick-x" aria-hidden>
            ✕
          </span>
        </button>
      </div>
    );
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setCursor((c) => Math.min(c + 1, Math.max(results.length - 1, 0)));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(c - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const hit = results[cursor];
      if (open && hit) select(hit);
    } else if (e.key === "Escape") {
      setOpen(false); // keeps focus: typing again reopens the list
    }
  };

  return (
    <div
      className="player-combo tac-pick"
      onBlur={() => {
        closeTimer.current = window.setTimeout(() => setOpen(false), 150);
      }}
      onFocus={() => {
        window.clearTimeout(closeTimer.current);
        setOpen(true);
      }}
    >
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        onKeyDown={onKeyDown}
        placeholder="Search an opponent…"
        autoComplete="off"
        spellCheck={false}
      />
      {open && (
        <div className="player-dropdown" ref={listRef}>
          {results.map((o, i) => (
            <button
              key={o.id}
              className={`player-option${i === cursor ? " is-active" : ""}`}
              onMouseDown={(e) => e.preventDefault()}
              onMouseEnter={() => setCursor(i)}
              onClick={() => select(o)}
            >
              <span className="player-name">{o.name}</span>
              <span className="tac-pick-meta">
                {describe(o)}
                {o.plays_pips ? " · pips" : ""}
              </span>
            </button>
          ))}
          {results.length === 0 && (
            <div className="player-hint">
              No singles opponent matches “{query.trim()}”.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
