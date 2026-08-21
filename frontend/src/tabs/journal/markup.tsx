// Lightweight formatting for journal text (user 2026-08-21: Ctrl+B/I/U,
// rendered live while typing via RichArea). Storage stays plain text with
// Markdown-style markers — **bold**, *italic*, __underline__ — so the DB,
// the AI-coach bundle, and the Tactics context keep reading ordinary
// strings; only the journal's display/editing layer renders the markers.
import type { ReactNode } from "react";

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

// ---- marker text ⇄ contentEditable HTML (RichArea's storage format) ----

const HTML_ESC: Record<string, string> = { "&": "&amp;", "<": "&lt;", ">": "&gt;" };
const escapeHtml = (s: string) => s.replace(/[&<>]/g, (c) => HTML_ESC[c]);

/** Marker text → minimal HTML (b/i/u + <br>) to seed a RichArea. */
export function markersToHtml(text: string): string {
  return text
    .split("\n")
    .map((line) =>
      line
        .split(MARKUP_RX)
        .map((p) => {
          if (p.startsWith("**") && p.endsWith("**") && p.length > 4)
            return `<b>${escapeHtml(p.slice(2, -2))}</b>`;
          if (p.startsWith("__") && p.endsWith("__") && p.length > 4)
            return `<u>${escapeHtml(p.slice(2, -2))}</u>`;
          if (p.startsWith("*") && p.endsWith("*") && p.length > 2)
            return `<i>${escapeHtml(p.slice(1, -1))}</i>`;
          return escapeHtml(p);
        })
        .join("")
    )
    .join("<br>");
}

/** contentEditable HTML → marker text. Handles what browsers actually
 * produce while editing: <b>/<strong>, <i>/<em>, <u>, <br>, and
 * div/p-per-line (Chrome); anything else contributes only its text. */
export function htmlToMarkers(html: string): string {
  const tpl = document.createElement("template");
  tpl.innerHTML = html;
  const out: string[] = [];
  const endsWithNewline = () =>
    out.length > 0 && out[out.length - 1].endsWith("\n");
  const walk = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      out.push((node.nodeValue ?? "").replace(/\u00a0/g, " "));
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const tag = (node as HTMLElement).tagName;
    if (tag === "BR") {
      out.push("\n");
      return;
    }
    // Chrome wraps every line after the first in a <div>; an empty line is
    // <div><br></div> (the prepended \n + the BR's \n = one blank line).
    if ((tag === "DIV" || tag === "P") && out.length > 0 && !endsWithNewline())
      out.push("\n");
    const marker =
      tag === "B" || tag === "STRONG"
        ? "**"
        : tag === "I" || tag === "EM"
          ? "*"
          : tag === "U"
            ? "__"
            : "";
    if (marker) out.push(marker);
    node.childNodes.forEach(walk);
    if (marker) out.push(marker);
  };
  tpl.content.childNodes.forEach(walk);
  // Empty marker pairs (bold toggled on, nothing typed) are noise.
  return out.join("").replace(/\*\*\*\*|____/g, "");
}
