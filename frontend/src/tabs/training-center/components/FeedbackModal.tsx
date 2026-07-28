import { useState } from "react";
import Modal from "../../../shared/ui/Modal";
import { addDays, toIso, todayIso } from "../../../shared/dates";
import type { Pain, Rpe } from "../types";

const PAIN: { key: Pain; label: string }[] = [
  { key: "none", label: "😀 No pain" },
  { key: "mild", label: "😐 Mild pain" },
  { key: "strong", label: "😣 Strong pain" },
];
const RPE: { key: Rpe; label: string }[] = [
  { key: "easy", label: "Easy" },
  { key: "medium", label: "Medium" },
  { key: "hard", label: "Hard" },
];

// Asked after a session: which day it was trained (default today, can backdate
// if logged late) + knee pain + perceived effort (drives autoregulation/safety).
export default function FeedbackModal({
  onSubmit,
  onClose,
}: {
  onSubmit: (pain: Pain, rpe: Rpe, doneOn: string) => void;
  onClose: () => void;
}) {
  // Computed per render (shared local-day helpers) so a tab left open across
  // midnight doesn't keep offering yesterday as "Today".
  const TODAY = todayIso();
  const YESTERDAY = toIso(addDays(new Date(), -1));
  const dateLabel = (iso: string) =>
    iso === TODAY ? "Today" : iso === YESTERDAY ? "Yesterday" : iso;

  const [pain, setPain] = useState<Pain>("none");
  const [rpe, setRpe] = useState<Rpe>("medium");
  const [doneOn, setDoneOn] = useState<string>(TODAY);
  return (
    <Modal title="How was the session?" onClose={onClose}>
      <div className="tc-fb">
        <div className="tc-fb-group">
          <div className="tc-fb-q">Which day did you train?</div>
          <div className="tc-fb-opts">
            <button
              className={`tc-fb-opt${doneOn === TODAY ? " active" : ""}`}
              onClick={() => setDoneOn(TODAY)}
            >
              Today
            </button>
            <button
              className={`tc-fb-opt${doneOn === YESTERDAY ? " active" : ""}`}
              onClick={() => setDoneOn(YESTERDAY)}
            >
              Yesterday
            </button>
            <input
              type="date"
              className="tc-fb-date"
              value={doneOn}
              max={TODAY}
              onChange={(e) => e.target.value && setDoneOn(e.target.value)}
            />
          </div>
          {doneOn !== TODAY && (
            <div className="tc-fb-hint">
              Logging for <b>{dateLabel(doneOn)}</b> (trained earlier, logged late).
            </div>
          )}
        </div>
        <div className="tc-fb-group">
          <div className="tc-fb-q">Any knee pain?</div>
          <div className="tc-fb-opts">
            {PAIN.map((p) => (
              <button
                key={p.key}
                className={`tc-fb-opt${pain === p.key ? " active" : ""}`}
                onClick={() => setPain(p.key)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
        <div className="tc-fb-group">
          <div className="tc-fb-q">Effort level?</div>
          <div className="tc-fb-opts">
            {RPE.map((r) => (
              <button
                key={r.key}
                className={`tc-fb-opt${rpe === r.key ? " active" : ""}`}
                onClick={() => setRpe(r.key)}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
        {pain === "strong" && (
          <div className="tc-fb-warn">
            ⚠️ With strong pain you should rest and consider seeing a
            doctor/PT. The next session will auto-reduce the load.
          </div>
        )}
        <button
          className="btn primary tc-fb-save"
          onClick={() => onSubmit(pain, rpe, doneOn)}
        >
          Save & complete session
        </button>
      </div>
    </Modal>
  );
}
