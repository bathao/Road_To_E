import { useState } from "react";
import { formatTarget, playTing } from "../constants";
import type { SessionItem, SimpleExercise, TrainingSession } from "../types";

function ExerciseThumb({ gif, alt }: { gif: string; alt: string }) {
  const [broken, setBroken] = useState(false);
  if (!gif || broken) {
    return <div className="tc-ex-thumb tc-ex-thumb-ph">🏋️</div>;
  }
  return (
    <img className="tc-ex-thumb" src={gif} alt={alt} onError={() => setBroken(true)} />
  );
}

function ExerciseCard({
  item,
  readOnly,
  onTick,
  onSubstitute,
  onSkip,
}: {
  item: SessionItem;
  readOnly: boolean;
  onTick: (done: boolean) => void;
  onSubstitute: (key: string) => void;
  onSkip: (skipped: boolean) => void;
}) {
  const toggle = () => {
    if (readOnly || item.skipped) return;
    if (!item.done) playTing();
    onTick(!item.done);
  };
  return (
    <div
      className={`tc-ex${item.done ? " tc-ex-done" : ""}${item.skipped ? " tc-ex-skipped" : ""}`}
    >
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
        {!readOnly && (
          <div className="tc-ex-actions">
            {item.alternatives.length > 0 && (
              <select
                className="tc-ex-swap"
                value=""
                onChange={(e) => e.target.value && onSubstitute(e.target.value)}
                title="Đổi sang bài khác nếu bài này khó/đau"
              >
                <option value="">↺ Đổi bài…</option>
                {item.alternatives.map((a) => (
                  <option key={a.key} value={a.key}>
                    {a.name_vi}
                  </option>
                ))}
              </select>
            )}
            <button
              className="tc-ex-skip"
              onClick={() => onSkip(!item.skipped)}
              title="Bỏ qua nếu bài này làm đau"
            >
              {item.skipped ? "↩ Bỏ qua (hoàn tác)" : "✕ Bỏ (đau)"}
            </button>
          </div>
        )}
      </div>
      {!item.skipped && (
        <button
          className={`tc-check${item.done ? " tc-check-on" : ""}`}
          onClick={toggle}
          disabled={readOnly}
          aria-pressed={item.done}
        >
          {item.done ? "✓ Đã xong" : "Check done"}
        </button>
      )}
    </div>
  );
}

function MiniList({ title, items }: { title: string; items: SimpleExercise[] }) {
  if (items.length === 0) return null;
  return (
    <div className="tc-mini">
      <div className="tc-mini-title">{title}</div>
      {items.map((e) => (
        <div key={e.exercise_key} className="tc-mini-row">
          <span>{e.name_vi}</span>
          <span className="tc-mini-target">
            {formatTarget(e.target, e.per_side)}
          </span>
        </div>
      ))}
    </div>
  );
}

interface Props {
  session: TrainingSession;
  readOnly: boolean;
  onTick: (itemId: number, done: boolean) => void;
  onComplete: () => void;
  onSubstitute?: (itemId: number, key: string) => void;
  onSkip?: (itemId: number, skipped: boolean) => void;
  onStart?: () => void;
}

export default function SessionCard({
  session,
  readOnly,
  onTick,
  onComplete,
  onSubstitute,
  onSkip,
  onStart,
}: Props) {
  const active = session.items.filter((it) => !it.skipped);
  const allDone = active.length > 0 && active.every((it) => it.done);
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

      {!readOnly && onStart && (
        <button className="btn primary tc-start" onClick={onStart}>
          ▶ Bắt đầu tập (có hướng dẫn)
        </button>
      )}

      <MiniList title="🔥 Khởi động" items={session.warmup} />

      <div className="tc-ex-list">
        {session.items.map((it) => (
          <ExerciseCard
            key={it.id}
            item={it}
            readOnly={readOnly}
            onTick={(done) => onTick(it.id, done)}
            onSubstitute={(key) => onSubstitute?.(it.id, key)}
            onSkip={(skipped) => onSkip?.(it.id, skipped)}
          />
        ))}
      </div>

      <MiniList title="🧊 Giãn cơ (cool-down)" items={session.cooldown} />

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
