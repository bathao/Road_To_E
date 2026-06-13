import { useState } from "react";
import Modal from "../../../shared/ui/Modal";
import type { Pain, Rpe } from "../types";

const PAIN: { key: Pain; label: string }[] = [
  { key: "none", label: "😀 Không đau" },
  { key: "mild", label: "😐 Đau nhẹ" },
  { key: "strong", label: "😣 Đau nhiều" },
];
const RPE: { key: Rpe; label: string }[] = [
  { key: "easy", label: "Dễ" },
  { key: "medium", label: "Vừa" },
  { key: "hard", label: "Khó" },
];

// Asked after a session: knee pain + perceived effort. Drives autoregulation
// (the next sessions adjust) and safety.
export default function FeedbackModal({
  onSubmit,
  onClose,
}: {
  onSubmit: (pain: Pain, rpe: Rpe) => void;
  onClose: () => void;
}) {
  const [pain, setPain] = useState<Pain>("none");
  const [rpe, setRpe] = useState<Rpe>("medium");
  return (
    <Modal title="Buổi tập thế nào?" onClose={onClose}>
      <div className="tc-fb">
        <div className="tc-fb-group">
          <div className="tc-fb-q">Khớp gối có đau không?</div>
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
          <div className="tc-fb-q">Mức gắng sức?</div>
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
            ⚠️ Đau nhiều thì nên nghỉ và cân nhắc gặp bác sĩ/PT. Buổi sau sẽ tự
            giảm tải.
          </div>
        )}
        <button
          className="btn primary tc-fb-save"
          onClick={() => onSubmit(pain, rpe)}
        >
          Lưu & hoàn thành buổi
        </button>
      </div>
    </Modal>
  );
}
