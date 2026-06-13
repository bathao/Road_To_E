import { useState } from "react";
import { formatTarget, playTing } from "../constants";
import type { SessionItem, TrainingSession } from "../types";

function ExerciseThumb({ gif, alt }: { gif: string; alt: string }) {
  const [broken, setBroken] = useState(false);
  if (!gif || broken) {
    // GIFs are bundled later; show a neutral placeholder meanwhile.
    return <div className="tc-ex-thumb tc-ex-thumb-ph">🏋️</div>;
  }
  return (
    <img
      className="tc-ex-thumb"
      src={gif}
      alt={alt}
      onError={() => setBroken(true)}
    />
  );
}

function ExerciseCard({
  item,
  readOnly,
  onTick,
}: {
  item: SessionItem;
  readOnly: boolean;
  onTick: (done: boolean) => void;
}) {
  const toggle = () => {
    if (readOnly) return;
    if (!item.done) playTing();
    onTick(!item.done);
  };
  return (
    <div className={`tc-ex${item.done ? " tc-ex-done" : ""}`}>
      <ExerciseThumb gif={item.gif} alt={item.name_vi} />
      <div className="tc-ex-body">
        <div className="tc-ex-head">
          <span className="tc-ex-name">{item.name_vi}</span>
          <span className="tc-ex-target">{formatTarget(item.target, item.per_side)}</span>
        </div>
        <div className="tc-ex-benefit">{item.tt_benefit}</div>
        {item.form_cue && <div className="tc-ex-cue">💡 {item.form_cue}</div>}
        {item.is_prescribed && (
          <div className="tc-ex-rx">
            🎯 HLV chỉ định{item.rx_reason ? ` — ${item.rx_reason}` : ""}
          </div>
        )}
      </div>
      <button
        className={`tc-check${item.done ? " tc-check-on" : ""}`}
        onClick={toggle}
        disabled={readOnly}
        aria-pressed={item.done}
      >
        {item.done ? "✓ Đã xong" : "Check done"}
      </button>
    </div>
  );
}

interface Props {
  session: TrainingSession;
  /** A completed session opened from the grid is shown read-only. */
  readOnly: boolean;
  onTick: (itemId: number, done: boolean) => void;
  onComplete: () => void;
}

export default function SessionCard({
  session,
  readOnly,
  onTick,
  onComplete,
}: Props) {
  const allDone = session.total > 0 && session.done_count === session.total;
  return (
    <section className="tc-session">
      <div className="tc-session-head">
        <h3>
          Day {session.day_index} · {session.focus_vi}
        </h3>
        <span className="tc-session-meta">
          ⏱ ~{session.est_minutes} phút · {session.done_count}/{session.total} bài
          {session.status === "done" && session.done_on
            ? ` · ✅ ${session.done_on}`
            : ""}
        </span>
      </div>

      <div className="tc-ex-list">
        {session.items.map((it) => (
          <ExerciseCard
            key={it.id}
            item={it}
            readOnly={readOnly}
            onTick={(done) => onTick(it.id, done)}
          />
        ))}
      </div>

      {!readOnly && (
        <div className="tc-session-foot">
          <button
            className="btn primary tc-complete"
            onClick={onComplete}
            disabled={session.status === "done"}
          >
            {session.status === "done"
              ? "Đã hoàn thành buổi"
              : allDone
                ? "🎉 Hoàn thành buổi"
                : "Hoàn thành buổi"}
          </button>
          {!allDone && session.status !== "done" && (
            <span className="tc-session-hint">
              Có thể chốt buổi kể cả khi chưa tick hết.
            </span>
          )}
        </div>
      )}
    </section>
  );
}
