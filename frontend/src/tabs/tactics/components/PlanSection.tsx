// The generated game plan (Vietnamese coach content) + the Generate button.
// Same job contract as the Head Coach verdict: `generating` polls until the
// backend flips it to done/error.
import { useState } from "react";
import { prettyDate } from "../../../shared/dates";
import type { TacticPlan } from "../types";

const SECTIONS: { key: keyof TacticPlan; title: string; icon: string }[] = [
  { key: "serve_receive", title: "Serve & receive", icon: "🏓" },
  { key: "rally", title: "Rally plan", icon: "🔁" },
  { key: "avoid", title: "Never do", icon: "🚫" },
  { key: "mental", title: "Mental keys", icon: "🧠" },
];

export default function PlanSection({
  plan,
  opponentName,
  onGenerate,
  onClear,
  busy,
}: {
  plan: TacticPlan | null;
  opponentName: string;
  onGenerate: () => void;
  // Forget every generated plan for this opponent (two-step confirm).
  onClear: () => void;
  busy: boolean;
}) {
  const generating = plan?.status === "generating";
  const [confirmClear, setConfirmClear] = useState(false);
  return (
    <section className="tac-plan">
      <div className="tac-sec-head">
        <h2>🧠 Game plan vs {opponentName}</h2>
        <button
          className="btn primary"
          disabled={busy || generating}
          onClick={onGenerate}
        >
          {generating
            ? "⏳ Coach is thinking…"
            : plan?.status === "done"
              ? "↻ Regenerate"
              : "Generate game plan"}
        </button>
      </div>

      {plan?.status === "error" && (
        <div className="error-banner">⚠ {plan.error_msg ?? "Generation failed."}</div>
      )}
      {(!plan || plan.status === "empty") && (
        <p className="tac-hint">
          No plan yet — add scouting facts (or run the interview), then let the
          coach build one.
        </p>
      )}
      {generating && (
        <p className="tac-hint">
          The coach is reading the head-to-head history and your scouting
          notes… this can take a minute on the local model.
        </p>
      )}

      {plan?.status === "done" && (
        <div className="tac-plan-body">
          <div className="tac-plan-headline">“{plan.headline}”</div>
          <p className="tac-plan-overall">{plan.overall}</p>
          <div className="tac-plan-grid">
            {SECTIONS.map((s) => {
              const items = plan[s.key] as string[];
              if (!items?.length) return null;
              return (
                <div key={s.key} className="tac-plan-card">
                  <h4>
                    {s.icon} {s.title}
                  </h4>
                  <ul>
                    {items.map((t, i) => (
                      <li key={i}>{t}</li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
          {plan.data_gaps.length > 0 && (
            <div className="tac-plan-gaps">
              <h4>🎤 The coach still wants to know</h4>
              <ul>
                {plan.data_gaps.map((t, i) => (
                  <li key={i}>{t}</li>
                ))}
              </ul>
              <p className="tac-hint">
                Answer these via the interview (or add facts by hand), then
                regenerate.
              </p>
            </div>
          )}
          <div className="tac-plan-meta">
            <span>
              {plan.created_at ? `Generated ${prettyDate(plan.created_at.slice(0, 10))}` : ""}
              {plan.model ? ` · ${plan.model}` : ""}
            </span>
            {confirmClear ? (
              <span className="tac-plan-clear">
                Forget this plan (the scouting file stays)?
                <button
                  className="btn danger"
                  disabled={busy}
                  onClick={() => { setConfirmClear(false); onClear(); }}
                >
                  Yes, clear it
                </button>
                <button className="btn" onClick={() => setConfirmClear(false)}>Keep</button>
              </span>
            ) : (
              <button
                className="btn"
                disabled={busy}
                title="Remove this plan — it was written on thin data; generate a new one later"
                onClick={() => setConfirmClear(true)}
              >
                🗑 Clear plan
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
