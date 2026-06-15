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

// Local (not UTC) ISO date — avoids slipping a day near midnight.
function localISO(d: Date): string {
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tz).toISOString().slice(0, 10);
}
const TODAY = localISO(new Date());
const YESTERDAY = localISO(new Date(Date.now() - 86400000));

function dateLabel(iso: string): string {
  if (iso === TODAY) return "Hôm nay";
  if (iso === YESTERDAY) return "Hôm qua";
  return iso;
}

// Asked after a session: which day it was trained (default today, can backdate
// if logged late) + knee pain + perceived effort (drives autoregulation/safety).
export default function FeedbackModal({
  onSubmit,
  onClose,
}: {
  onSubmit: (pain: Pain, rpe: Rpe, doneOn: string) => void;
  onClose: () => void;
}) {
  const [pain, setPain] = useState<Pain>("none");
  const [rpe, setRpe] = useState<Rpe>("medium");
  const [doneOn, setDoneOn] = useState<string>(TODAY);
  return (
    <Modal title="Buổi tập thế nào?" onClose={onClose}>
      <div className="tc-fb">
        <div className="tc-fb-group">
          <div className="tc-fb-q">Tập ngày nào?</div>
          <div className="tc-fb-opts">
            <button
              className={`tc-fb-opt${doneOn === TODAY ? " active" : ""}`}
              onClick={() => setDoneOn(TODAY)}
            >
              Hôm nay
            </button>
            <button
              className={`tc-fb-opt${doneOn === YESTERDAY ? " active" : ""}`}
              onClick={() => setDoneOn(YESTERDAY)}
            >
              Hôm qua
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
              Ghi cho <b>{dateLabel(doneOn)}</b> (tập trễ, track lại sau).
            </div>
          )}
        </div>
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
          onClick={() => onSubmit(pain, rpe, doneOn)}
        >
          Lưu & hoàn thành buổi
        </button>
      </div>
    </Modal>
  );
}
