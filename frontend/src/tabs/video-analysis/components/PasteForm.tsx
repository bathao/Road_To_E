import { useState } from "react";
import type { ModelHealth, Setting } from "../types";
import { SETTING_LABEL } from "../labels";

// Local (not UTC) ISO date — avoids slipping a day near midnight.
function localISO(d: Date): string {
  const tz = d.getTimezoneOffset() * 60000;
  return new Date(d.getTime() - tz).toISOString().slice(0, 10);
}
const TODAY = localISO(new Date());
const YESTERDAY = localISO(new Date(Date.now() - 86400000));

interface Props {
  health: ModelHealth | null;
  submitting: boolean;
  onCreate: (form: {
    source_text: string;
    analysis_date: string;
    setting: Setting;
    title: string;
    context: string;
  }) => Promise<void>;
}

export default function PasteForm({ health, submitting, onCreate }: Props) {
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [context, setContext] = useState("");
  const [date, setDate] = useState(TODAY);
  const [setting, setSetting] = useState<Setting>("practice");

  const submit = async () => {
    if (!text.trim()) return;
    await onCreate({
      source_text: text.trim(),
      analysis_date: date,
      setting,
      title: title.trim(),
      context: context.trim(),
    });
    setText("");
    setTitle("");
    setContext("");
    setDate(TODAY);
    setSetting("practice");
  };

  const modelBad = health && !health.default_available;

  return (
    <section className="va-card">
      <div className="va-card-head">
        <h3>📋 Dán bản phân tích</h3>
        {health && (
          <span className={`va-chip ${health.default_available ? "va-ok" : "va-warn"}`}>
            {health.ollama_up ? health.default_model : "Ollama tắt"}
          </span>
        )}
      </div>
      <p className="va-muted">
        Phân tích video ở công cụ khác (trên cloud) rồi <b>dán kết quả text</b> vào
        đây, kèm <b>ngày</b> của buổi đó. Hệ thống bóc tách thành nhận xét, <b>tự
        lưu</b> và <b>tự cập nhật điểm kỹ năng (Tập/Đấu)</b> (bạn có thể sửa/xóa sau).
      </p>
      {modelBad && <div className="va-warn">⚠️ {health?.message}</div>}

      <div className="tc-fb-group">
        <div className="tc-fb-q">Bối cảnh clip?</div>
        <div className="tc-fb-opts">
          {(["practice", "match"] as Setting[]).map((s) => (
            <button
              key={s}
              className={`tc-fb-opt${setting === s ? " active" : ""}`}
              onClick={() => setSetting(s)}
            >
              {s === "practice" ? "🏓 Tập luyện / khởi động" : "🔥 Thi đấu trận thật"}
            </button>
          ))}
        </div>
        <div className="tc-fb-hint">
          Tách <b>{SETTING_LABEL[setting]}</b> để HLV thấy rõ chênh lệch giữa lúc tập và lúc đấu.
        </div>
      </div>

      <div className="tc-fb-group">
        <div className="tc-fb-q">Phân tích của ngày nào?</div>
        <div className="tc-fb-opts">
          <button
            className={`tc-fb-opt${date === TODAY ? " active" : ""}`}
            onClick={() => setDate(TODAY)}
          >
            Hôm nay
          </button>
          <button
            className={`tc-fb-opt${date === YESTERDAY ? " active" : ""}`}
            onClick={() => setDate(YESTERDAY)}
          >
            Hôm qua
          </button>
          <input
            type="date"
            className="tc-fb-date"
            value={date}
            max={TODAY}
            onChange={(e) => e.target.value && setDate(e.target.value)}
          />
        </div>
      </div>

      <div className="va-form-grid">
        <label>Tiêu đề (tùy chọn)
          <input className="pb-input" value={title} placeholder="vd: Trận giao hữu CN"
            onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>Bối cảnh (tùy chọn)
          <input className="pb-input" value={context} placeholder="vd: tập giao bóng, trận giải…"
            onChange={(e) => setContext(e.target.value)} />
        </label>
      </div>

      <textarea
        className="pb-input va-paste-area"
        value={text}
        placeholder="Dán toàn bộ nội dung phân tích ở đây…"
        rows={10}
        onChange={(e) => setText(e.target.value)}
      />

      <div className="va-row-end">
        <button className="btn primary" disabled={submitting || !text.trim()} onClick={submit}>
          {submitting ? "Đang lưu…" : "Bóc tách & lưu"}
        </button>
      </div>
    </section>
  );
}
