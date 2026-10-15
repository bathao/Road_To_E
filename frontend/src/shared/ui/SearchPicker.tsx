import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { fold } from "../fold";

// Type-to-search picker over an already-loaded list: an input that filters
// client-side, diacritic-insensitive ("vy" → "Nguyễn Phúc Hoàng Vy"), with
// an empty query listing everything in the caller's order so browsing still
// works; once something is picked it turns into a pill, click it to pick
// someone else. Born as the Tactics tab's OpponentPicker (2026-10-10),
// generalised 2026-10-15 so the Profile tab's Head-to-head lookup (129
// opponents in a plain <select>) gets the same combo. Nothing can be ADDED
// here — the Daily Tracker's PlayerPicker is the one that creates players.
// Reuses the .player-combo / .player-dropdown / .player-option look.
export interface SearchPickerItem {
  id: number;
  name: string;
}

export default function SearchPicker<T extends SearchPickerItem>({
  items,
  selected,
  onPick,
  describe,
  pillExtra,
  placeholder = "Search…",
  emptyText,
  className = "",
}: {
  items: T[];
  selected: T | null;
  onPick: (id: number | null) => void;
  // Muted text after the name; `where` lets a caller add list-only detail
  // that the pill carries as a chip instead.
  describe: (item: T, where: "list" | "pill") => string;
  // Extra chips rendered inside the pill (e.g. "🏓 Pips").
  pillExtra?: (item: T) => ReactNode;
  placeholder?: string;
  // Shown when the query matches nothing; receives the trimmed query.
  emptyText: (query: string) => string;
  className?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const closeTimer = useRef<number | undefined>(undefined);

  const results = useMemo(() => {
    const q = fold(query.trim());
    if (!q) return items;
    return items.filter((o) => fold(o.name).includes(q));
  }, [items, query]);

  // Keep the keyboard cursor inside the (shrinking) result list and the
  // highlighted row in view.
  useEffect(() => {
    setCursor(0);
  }, [query]);
  useEffect(() => {
    const el = listRef.current?.children[cursor] as HTMLElement | undefined;
    el?.scrollIntoView({ block: "nearest" });
  }, [cursor, open]);

  const select = (o: T) => {
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
      <div className={`spick ${className}`.trim()}>
        <button className="spick-pill" title="Pick someone else" onClick={clear}>
          <span className="player-name">{selected.name}</span>
          <span className="spick-meta">· {describe(selected, "pill")}</span>
          {pillExtra?.(selected)}
          <span className="spick-x" aria-hidden>
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
      className={`player-combo spick ${className}`.trim()}
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
        placeholder={placeholder}
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
              <span className="spick-meta">{describe(o, "list")}</span>
            </button>
          ))}
          {results.length === 0 && (
            <div className="player-hint">{emptyText(query.trim())}</div>
          )}
        </div>
      )}
    </div>
  );
}
