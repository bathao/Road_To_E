import { useState } from "react";

// Free-text note for a day. The grid cell only shows a short preview; the full
// text is written here.
export default function NoteEditor({
  current,
  onSave,
}: {
  current: string;
  onSave: (text: string) => void;
}) {
  const [text, setText] = useState(current);

  return (
    <div className="editor">
      <p className="editor-sub">Things to note for this day</p>
      <textarea
        className="note-area"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="e.g. fix serve contact point; right shoulder sore, ease off next session…"
        rows={6}
        autoFocus
      />
      <div className="note-actions">
        {current && (
          <button className="btn danger" onClick={() => onSave("")}>
            Clear
          </button>
        )}
        <button className="btn primary" onClick={() => onSave(text)}>
          Save
        </button>
      </div>
    </div>
  );
}
