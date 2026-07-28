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
      sub: "🔥 Warm-up",
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
        const sides = it.per_side ? ["Left side", "Right side"] : [""];
        sides.forEach((side, si) => {
          const isLastSub = si === sides.length - 1;
          steps.push({
            type: "timed",
            title: it.name_vi,
            sub: `Set ${s}/${sets}${side ? " · " + side : ""}`,
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
          sub: `Set ${s}/${sets}`,
          gif: it.gif,
          cue: it.form_cue,
          reps: it.target.reps ?? 0,
          perSide: it.per_side,
          itemId: lastSet ? it.id : undefined,
        });
      }
      if (!isLastMainStep) {
        const next = lastSet
          ? items[ii + 1]?.name_vi ?? "next exercise"
          : it.name_vi;
        steps.push({ type: "rest", sec: REST_SEC, nextTitle: next });
      }
    }
  });
  for (const c of session.cooldown) {
    steps.push({
      type: "timed",
      title: c.name_vi,
      sub: "🧊 Cool-down",
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
  const [secLeft, setSecLeft] = useState(-1); // -1 = no countdown on this step yet
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

  // (Re)load the countdown when the step changes. -1 = no countdown running.
  useEffect(() => {
    setSecLeft(step && (step.type === "timed" || step.type === "rest") ? step.sec : -1);
  }, [idx]); // eslint-disable-line react-hooks/exhaustive-deps

  // Tick the countdown once per second. The updater stays PURE (React may
  // double-invoke it); side effects (ting + advance) run in the effect below
  // when the counter reaches zero.
  useEffect(() => {
    if (!step || (step.type !== "timed" && step.type !== "rest")) return;
    if (paused) return;
    const id = setInterval(() => {
      setSecLeft((s) => (s > 0 ? s - 1 : s));
    }, 1000);
    return () => clearInterval(id);
  }, [idx, paused]); // eslint-disable-line react-hooks/exhaustive-deps

  // Countdown reached zero → ting + auto-advance (side effects live here).
  useEffect(() => {
    if (secLeft !== 0 || !step || (step.type !== "timed" && step.type !== "rest")) return;
    playTing();
    advance();
  }, [secLeft]); // eslint-disable-line react-hooks/exhaustive-deps

  // Exclude the 'done' step; max(1) so an all-skipped session can't divide by 0.
  const total = Math.max(1, steps.length - 1);
  const progress = Math.round((Math.min(idx, total) / total) * 100);

  return (
    <div className="tc-wp-overlay" role="dialog" aria-modal="true">
      <div className="tc-wp">
        <div className="tc-wp-top">
          <div className="tc-wp-bar">
            <div className="tc-wp-bar-fill" style={{ width: `${progress}%` }} />
          </div>
          <button className="tc-wp-close" onClick={onClose} aria-label="Exit">
            ✕
          </button>
        </div>

        {step.type === "done" ? (
          <div className="tc-wp-body tc-wp-done">
            <div className="tc-wp-done-emoji">🎉</div>
            <h2>Session complete!</h2>
            <p className="tc-muted">Tap to log the session & give feedback.</p>
            <button className="btn primary tc-wp-finish" onClick={onFinish}>
              Complete session
            </button>
          </div>
        ) : step.type === "rest" ? (
          <div className="tc-wp-body tc-wp-rest">
            <div className="tc-wp-sub">Rest</div>
            <div className="tc-wp-timer">{Math.max(secLeft, 0)}s</div>
            <div className="tc-wp-next">Next: {step.nextTitle}</div>
            <div className="tc-wp-controls">
              <button className="btn" onClick={() => setPaused((p) => !p)}>
                {paused ? "▶ Resume" : "⏸ Pause"}
              </button>
              <button className="btn primary" onClick={() => advance()}>
                Skip rest ▸
              </button>
            </div>
          </div>
        ) : (
          <div className="tc-wp-body">
            {/* key: consecutive steps reuse this tree position — remount so
                one step's failed-GIF fallback doesn't stick to the next. */}
            <ExerciseImage
              key={step.gif}
              gif={step.gif}
              alt={step.title}
              className="tc-wp-thumb"
            />
            <div className="tc-wp-sub">{step.sub}</div>
            <h2 className="tc-wp-title">{step.title}</h2>
            {step.type === "timed" ? (
              <>
                <div className="tc-wp-timer">{Math.max(secLeft, 0)}s</div>
                <div className="tc-wp-controls">
                  <button className="btn" onClick={() => setPaused((p) => !p)}>
                    {paused ? "▶ Resume" : "⏸ Pause"}
                  </button>
                  <button className="btn primary" onClick={() => advance()}>
                    Done ▸
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="tc-wp-reps">
                  {step.reps} reps{step.perSide ? " / each side" : ""}
                </div>
                <div className="tc-wp-controls">
                  <button className="btn primary tc-wp-big" onClick={() => advance()}>
                    ✓ Set done
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
