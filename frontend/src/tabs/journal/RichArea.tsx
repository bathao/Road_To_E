// Minimal WYSIWYG writing area for the Journal (user 2026-08-21: "trong
// khung edit nó ko hiện in đậm được à?"). A contentEditable div where
// Ctrl+B/I/U format the selection LIVE; the value in/out stays the same
// marker plain text the rest of the app uses (markersToHtml/htmlToMarkers).
// Deliberately tiny — bold/italic/underline + newlines only, paste forced
// to plain text — to stay friendly to the Vietnamese IME and the browser's
// native undo. The DOM is only rewritten on EXTERNAL value changes (e.g.
// the draft clearing after Save day), never while the user is typing.
import { useEffect, useRef } from "react";
import type { KeyboardEvent } from "react";
import { htmlToMarkers, markersToHtml } from "./markup";

const HOTKEY_CMDS: Record<string, string> = {
  b: "bold",
  i: "italic",
  u: "underline",
};

export default function RichArea({
  value,
  onChange,
  placeholder = "",
  className = "",
  autoFocus = false,
  onEscape,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  autoFocus?: boolean;
  onEscape?: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  // The last value WE emitted — an incoming value that matches it is just
  // our own edit echoing back through state; rewriting the DOM for it
  // would destroy the caret (and any in-progress IME composition).
  const lastEmitted = useRef<string | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (el && value !== lastEmitted.current) {
      el.innerHTML = markersToHtml(value);
      lastEmitted.current = value;
    }
  }, [value]);

  useEffect(() => {
    if (!autoFocus) return;
    const el = ref.current;
    if (!el) return;
    el.focus();
    // Caret at the end (focus alone puts it at the start).
    const sel = window.getSelection();
    if (sel) {
      const range = document.createRange();
      range.selectNodeContents(el);
      range.collapse(false);
      sel.removeAllRanges();
      sel.addRange(range);
    }
  }, [autoFocus]);

  const emit = () => {
    const el = ref.current;
    if (!el) return;
    const v = htmlToMarkers(el.innerHTML);
    lastEmitted.current = v;
    onChange(v);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && !e.altKey) {
      const cmd = HOTKEY_CMDS[e.key.toLowerCase()];
      if (cmd) {
        e.preventDefault();
        // execCommand is deprecated but has no same-weight replacement for
        // selection formatting; every target browser still ships it.
        document.execCommand(cmd);
        emit();
        return;
      }
    }
    if (e.key === "Escape") onEscape?.();
  };

  return (
    <div
      ref={ref}
      className={`jr-input jr-rich ${className}`}
      contentEditable
      role="textbox"
      aria-multiline="true"
      data-placeholder={placeholder}
      data-empty={value.trim() === "" ? "true" : "false"}
      onInput={emit}
      onKeyDown={onKeyDown}
      onPaste={(e) => {
        // Plain text only — no smuggling colors/fonts in from other apps.
        e.preventDefault();
        document.execCommand(
          "insertText",
          false,
          e.clipboardData.getData("text/plain")
        );
      }}
      suppressContentEditableWarning
    />
  );
}
