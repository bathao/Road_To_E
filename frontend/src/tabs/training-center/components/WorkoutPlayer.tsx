import { useEffect, useMemo, useRef, useState } from "react";
import { playTing } from "../constants";
import type { TrainingSession } from "../types";
import ExerciseImage from "./ExerciseImage";

// One step in the guided run: warm-up / work set / rest / cooldown / done.
type Step =
  | {
      type: "timed";
      title: string;
      sub: string;
      gif: string;
      cue?: string;
      sec: number;
      itemId?: number; // set on the LAST work step of an item -> tick it done
    }
  | {
      type: "reps";
      title: string;
      sub: string;
      gif: string;
      cue?: string;
      reps: number;
      perSide: boolean;
      itemId?: number;
    }
  | { type: "rest"; sec: number; nextTitle: string }
  | { type: "done" };

const REST_SEC = 20;

function buildSteps(session: TrainingSession): Step[] {
  const steps: Step[] = [];
  for (const w of session.warmup) {
    steps.push({
      type: "timed",
      title: w.name_vi,
      sub: "🔥 Khởi động",
      gif: w.gif,
      cue: w.form_cue,
      sec: w.target.sec ?? 40,
    });
  }
  const items = session.items.filter((it) => !it.skipped);
  items.forEach((it, ii) => {
    const sets = it.target.sets ?? 1;
    for (let s = 1; s <= sets; s++) {
      const lastSet = s === sets;
      const isLastMainStep = ii === items.length - 1 && lastSet;
      if (it.kind === "timed") {
        const sec = it.target.sec ?? 30;
        const sides = it.per_side ? ["Bên trái", "Bên phải"] : [""];
        sides.forEach((side, si) => {
          const isLastSub = si === sides.length - 1;
          steps.push({
            type: "timed",
            title: it.name_vi,
            sub: `Hiệp ${s}/${sets}${side ? " · " + side : ""}`,
            gif: it.gif,
            cue: it.form_cue,
            sec,
            itemId: lastSet && isLastSub ? it.id : undefined,
          });
        });
      } else {
        steps.push({
          type: "reps",
          title: it.name_vi,
          sub: `Hiệp ${s}/${sets}`,
          gif: it.gif,
          cue: it.form_cue,
          reps: it.target.reps ?? 0,
          perSide: it.per_side,
          itemId: lastSet ? it.id : undefined,
        });
      }
      if (!isLastMainStep) {
        const next = lastSet
          ? items[ii + 1]?.name_vi ?? "bài tiếp"
          : it.name_vi;
        steps.push({ type: "rest", sec: REST_SEC, nextTitle: next });
      }
    }
  });
  for (const c of session.cooldown) {
    steps.push({
      type: "timed",
      title: c.name_vi,
      sub: "🧊 Giãn cơ",
      gif: c.gif,
      cue: c.form_cue,
      sec: c.target.sec ?? 40,
    });
  }
  steps.push({ type: "done" });
  return steps;
}

interface Props {
  session: TrainingSession;
  onTickItem: (itemId: number, done: boolean) => void;
  onFinish: () => void;
  onClose: () => void;
}

export default function WorkoutPlayer({
  session,
  onTickItem,
  onFinish,
  onClose,
}: Props) {
  const steps = useMemo(() => buildSteps(session), [session]);
  const [idx, setIdx] = useState(0);
  const [secLeft, setSecLeft] = useState(0);
  const [paused, setPaused] = useState(false);
  const tickedRef = useRef<Set<number>>(new Set());

  const step = steps[idx];

  // Advance to the next step, ticking the item done when leaving its last set.
  const advance = (cur = idx) => {
    const s = steps[cur];
    if (s && (s.type === "timed" || s.type === "reps") && s.itemId != null) {
      if (!tickedRef.current.has(s.itemId)) {
        tickedRef.current.add(s.itemId);
        onTickItem(s.itemId, true);
      }
    }
    setIdx((i) => Math.min(i + 1, steps.length - 1));
  };

  // (Re)load the countdown when the step changes.
  useEffect(() => {
    if (step && (step.type === "timed" || step.type === "rest")) {
      setSecLeft(step.sec);
    }
  }, [idx]); // eslint-disable-line react-hooks/exhaustive-deps

  // Tick the countdown once per second; auto-advance + ting at zero.
  useEffect(() => {
    if (!step || (step.type !== "timed" && step.type !== "rest")) return;
    if (paused) return;
    const id = setInterval(() => {
      setSecLeft((s) => {
        if (s <= 1) {
          clearInterval(id);
          playTing();
          advance();
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [idx, paused]); // eslint-disable-line react-hooks/exhaustive-deps

  const total = steps.length - 1; // exclude the 'done' step
  const progress = Math.round((Math.min(idx, total) / total) * 100);

  return (
    <div className="tc-wp-overlay" role="dialog" aria-modal="true">
      <div className="tc-wp">
        <div className="tc-wp-top">
          <div className="tc-wp-bar">
            <div className="tc-wp-bar-fill" style={{ width: `${progress}%` }} />
          </div>
          <button className="tc-wp-close" onClick={onClose} aria-label="Thoát">
            ✕
          </button>
        </div>

        {step.type === "done" ? (
          <div className="tc-wp-body tc-wp-done">
            <div className="tc-wp-done-emoji">🎉</div>
            <h2>Xong buổi tập!</h2>
            <p className="tc-muted">Bấm để ghi nhận & nhận phản hồi.</p>
            <button className="btn primary tc-wp-finish" onClick={onFinish}>
              Hoàn thành buổi
            </button>
          </div>
        ) : step.type === "rest" ? (
          <div className="tc-wp-body tc-wp-rest">
            <div className="tc-wp-sub">Nghỉ</div>
            <div className="tc-wp-timer">{secLeft}s</div>
            <div className="tc-wp-next">Tiếp theo: {step.nextTitle}</div>
            <div className="tc-wp-controls">
              <button className="btn" onClick={() => setPaused((p) => !p)}>
                {paused ? "▶ Tiếp tục" : "⏸ Tạm dừng"}
              </button>
              <button className="btn primary" onClick={() => advance()}>
                Bỏ nghỉ ▸
              </button>
            </div>
          </div>
        ) : (
          <div className="tc-wp-body">
            <ExerciseImage gif={step.gif} alt={step.title} className="tc-wp-thumb" />
            <div className="tc-wp-sub">{step.sub}</div>
            <h2 className="tc-wp-title">{step.title}</h2>
            {step.type === "timed" ? (
              <>
                <div className="tc-wp-timer">{secLeft}s</div>
                <div className="tc-wp-controls">
                  <button className="btn" onClick={() => setPaused((p) => !p)}>
                    {paused ? "▶ Tiếp tục" : "⏸ Tạm dừng"}
                  </button>
                  <button className="btn primary" onClick={() => advance()}>
                    Xong ▸
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="tc-wp-reps">
                  {step.reps} lần{step.perSide ? " / mỗi bên" : ""}
                </div>
                <div className="tc-wp-controls">
                  <button className="btn primary tc-wp-big" onClick={() => advance()}>
                    ✓ Xong hiệp
                  </button>
                </div>
              </>
            )}
            {step.cue && <div className="tc-wp-cue">💡 {step.cue}</div>}
          </div>
        )}
      </div>
    </div>
  );
}
