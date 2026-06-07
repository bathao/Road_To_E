import type { Clip } from "../types";
import { CLIP_TYPE_LABEL, STATUS_LABEL } from "../labels";

interface Props {
  clips: Clip[];
  selectedId: number | null;
  onSelect: (id: number) => void;
}

export default function ClipList({ clips, selectedId, onSelect }: Props) {
  if (clips.length === 0) {
    return <p className="va-muted">Chưa có clip nào.</p>;
  }
  return (
    <ul className="va-clip-list">
      {clips.map((c) => (
        <li
          key={c.id}
          className={`va-clip-item${selectedId === c.id ? " active" : ""}`}
          onClick={() => onSelect(c.id)}
        >
          <div className="va-clip-main">
            <span className="va-clip-title">{c.title || c.original_name}</span>
            <span className="va-muted va-clip-meta">
              {CLIP_TYPE_LABEL[c.clip_type]}
              {c.duration_sec ? ` · ${Math.round(c.duration_sec)}s` : ""}
            </span>
          </div>
          <span className={`va-status va-status-${c.status}`}>
            {STATUS_LABEL[c.status] ?? c.status}
          </span>
        </li>
      ))}
    </ul>
  );
}
