// A single tactic card. Two modes:
//  - "owned":   a My-Tactic — shows confidence stars + favorite, edit/delete.
//  - "library": a reference item — shows an "Add to My Tactics" / "Added" action.
import { PHASE_ICON } from "../constants";
import type { PhaseKey } from "../types";

interface CardData {
  phase: PhaseKey;
  title: string;
  when_to_use: string | null;
  how_to: string | null;
  follow_up: string | null;
  risk: string | null;
  opponent_styles: string[];
  tags: string[];
  source?: string | null;
  source_url?: string | null;
}

interface OwnedProps {
  mode: "owned";
  data: CardData;
  confidence: number;
  isFavorite: boolean;
  showPhaseIcon?: boolean;
  onToggleFavorite: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

interface LibraryProps {
  mode: "library";
  data: CardData;
  added: boolean;
  showPhaseIcon?: boolean;
  onAdd: () => void;
}

type Props = OwnedProps | LibraryProps;

function Field({ label, value }: { label: string; value: string | null }) {
  if (!value) return null;
  return (
    <div className="pb-field">
      <span className="pb-field-label">{label}</span>
      <span className="pb-field-value">{value}</span>
    </div>
  );
}

function Stars({ value }: { value: number }) {
  if (value <= 0) return null;
  return (
    <span className="pb-stars" title={`Tự tin ${value}/5`}>
      {"★".repeat(value)}
      <span className="pb-stars-dim">{"★".repeat(5 - value)}</span>
    </span>
  );
}

export default function TacticCard(props: Props) {
  const { data, showPhaseIcon } = props;
  const chips = [
    ...data.tags.map((t) => ({ text: t, kind: "tag" as const })),
    ...data.opponent_styles.map((t) => ({ text: t, kind: "opp" as const })),
  ];

  return (
    <div className={`pb-card${props.mode === "library" ? " pb-card-lib" : ""}`}>
      <div className="pb-card-head">
        <h4 className="pb-card-title">
          {showPhaseIcon && (
            <span className="pb-card-phase">{PHASE_ICON[data.phase]}</span>
          )}
          {data.title}
        </h4>
        {props.mode === "owned" ? (
          <div className="pb-card-actions">
            <Stars value={props.confidence} />
            <button
              className={`icon-btn pb-fav${props.isFavorite ? " on" : ""}`}
              title={props.isFavorite ? "Bỏ ghim" : "Ghim yêu thích"}
              onClick={props.onToggleFavorite}
            >
              {props.isFavorite ? "★" : "☆"}
            </button>
            <button className="icon-btn" title="Sửa" onClick={props.onEdit}>
              ✎
            </button>
            <button
              className="icon-btn danger"
              title="Xoá"
              onClick={props.onDelete}
            >
              🗑
            </button>
          </div>
        ) : props.added ? (
          <span className="pb-added">✓ Đã thêm</span>
        ) : (
          <button className="btn primary pb-add-btn" onClick={props.onAdd}>
            ↑ Thêm
          </button>
        )}
      </div>

      <Field label="When" value={data.when_to_use} />
      <Field label="How" value={data.how_to} />
      <Field label="Next" value={data.follow_up} />
      <Field label="Risk" value={data.risk} />

      {chips.length > 0 && (
        <div className="pb-chips">
          {chips.map((c, i) => (
            <span key={`${c.kind}-${i}`} className={`pb-chip pb-chip-${c.kind}`}>
              {c.text}
            </span>
          ))}
        </div>
      )}

      {props.mode === "library" && data.source && (
        <p className="pb-source">
          Nguồn:{" "}
          {data.source_url ? (
            <a href={data.source_url} target="_blank" rel="noreferrer">
              {data.source}
            </a>
          ) : (
            data.source
          )}
        </p>
      )}
    </div>
  );
}
