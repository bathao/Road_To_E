// Lightweight formatting for journal text (user 2026-08-21: Ctrl+B/I/U in
// the edit boxes). Storage stays plain text with Markdown-style markers —
// **bold**, *italic*, __underline__ — so the DB, the AI-coach bundle, and
// the Tactics context keep reading ordinary strings; only the journal's
// display layer renders the markers.
import type { KeyboardEvent, ReactNode } from "react";

const HOTKEY_MARKERS: Record<string, string> = { b: "**", i: "*", u: "__" };

/** Ctrl/Cmd+B/I/U inside a textarea: toggle the marker around the selection
 * (an empty selection gets an empty pair with the caret inside). Returns
 * true when the event was handled — callers skip their own key handling. */
export function formatHotkeys(
  e: KeyboardEvent<HTMLTextAreaElement>,
  sync: (value: string) => void
): boolean {
  if (!(e.ctrlKey || e.metaKey) || e.altKey) return false;
  const marker = HOTKEY_MARKERS[e.key.toLowerCase()];
  if (!marker) return false;
  e.preventDefault();
  const ta = e.currentTarget;
  const s = ta.selectionStart;
  const en = ta.selectionEnd;
  const value = ta.value;
  const sel = value.slice(s, en);

  // Toggle off when the selection sits inside (or includes) the markers.
  if (
    sel.startsWith(marker) &&
    sel.endsWith(marker) &&
    sel.length >= marker.length * 2
  ) {
    const inner = sel.slice(marker.length, sel.length - marker.length);
    ta.setRangeText(inner, s, en);
    ta.setSelectionRange(s, s + inner.length);
  } else if (
    value.slice(s - marker.length, s) === marker &&
    value.slice(en, en + marker.length) === marker
  ) {
    ta.setRangeText(sel, s - marker.length, en + marker.length);
    ta.setSelectionRange(s - marker.length, s - marker.length + sel.length);
  } else {
    ta.setRangeText(marker + sel + marker, s, en);
    if (sel) ta.setSelectionRange(s, s + sel.length + marker.length * 2);
    else ta.setSelectionRange(s + marker.length, s + marker.length);
  }
  sync(ta.value);
  return true;
}

const MARKUP_RX = /(\*\*[^*\n][^*]*?\*\*|__[^_\n][^_]*?__|\*[^*\n]+?\*)/g;

/** Render marker text as real formatting (no nesting — markers inside
 * markers stay literal, which is fine for diary prose). */
export function renderMarkup(text: string): ReactNode {
  const parts = text.split(MARKUP_RX);
  if (parts.length === 1) return text;
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**") && p.length > 4)
      return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("__") && p.endsWith("__") && p.length > 4)
      return <u key={i}>{p.slice(2, -2)}</u>;
    if (p.startsWith("*") && p.endsWith("*") && p.length > 2)
      return <em key={i}>{p.slice(1, -1)}</em>;
    return p;
  });
}
