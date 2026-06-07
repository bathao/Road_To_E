import { useState } from "react";
import type { ClipType, ModelHealth, Side } from "../types";
import { CLIP_TYPE_LABEL, SIDE_LABEL, SIDE_ORDER } from "../labels";

interface Props {
  health: ModelHealth | null;
  uploading: boolean;
  onBrowse: () => Promise<string>;
  onCreate: (form: {
    local_path: string;
    clip_type: ClipType;
    title: string;
    note?: string;
    model?: string;
    trim_start?: string;
    trim_end?: string;
    me_side?: Side;
    me_appearance?: string;
  }) => Promise<void>;
}

export default function UploadForm({ health, uploading, onBrowse, onCreate }: Props) {
  const [localPath, setLocalPath] = useState("");
  const [browsing, setBrowsing] = useState(false);
  const [clipType, setClipType] = useState<ClipType>("training");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [model, setModel] = useState("");
  const [trimStart, setTrimStart] = useState("");
  const [trimEnd, setTrimEnd] = useState("");
  const [meSide, setMeSide] = useState<Side>("");
  const [meAppearance, setMeAppearance] = useState("");

  const defaultModel = health?.default_model ?? "qwen3-vl:8b";
  const models = health?.models?.length ? health.models : [defaultModel];

  const hasSource = !!localPath.trim();

  const browse = async () => {
    setBrowsing(true);
    try {
      const path = await onBrowse();
      if (path) setLocalPath(path);
    } finally {
      setBrowsing(false);
    }
  };

  const submit = async () => {
    if (!hasSource) return;
    await onCreate({
      local_path: localPath.trim(),
      clip_type: clipType,
      title,
      note: note || undefined,
      model: model || undefined,
      trim_start: trimStart || undefined,
      trim_end: trimEnd || undefined,
      me_side: meSide || undefined,
      me_appearance: meAppearance || undefined,
    });
    setLocalPath("");
    setTitle("");
    setNote("");
    setTrimStart("");
    setTrimEnd("");
    setMeAppearance("");
  };

  return (
    <section className="va-card">
      <div className="va-card-head">
        <h3>🎬 Thêm clip (từ file trên máy)</h3>
      </div>

      <div className="va-upload-grid">
        <label className="va-col-span">
          File video
          <div className="va-file-row">
            <button type="button" className="btn" disabled={browsing} onClick={browse}>
              {browsing ? "Đang mở…" : "📁 Chọn file…"}
            </button>
            <input className="pb-input" value={localPath} placeholder="Chọn file hoặc dán đường dẫn…"
              onChange={(e) => setLocalPath(e.target.value)} />
          </div>
        </label>

        <label>Cắt từ (mm:ss)
          <input className="pb-input" value={trimStart} placeholder="vd: 12:30"
            onChange={(e) => setTrimStart(e.target.value)} />
        </label>
        <label>Đến (mm:ss)
          <input className="pb-input" value={trimEnd} placeholder="vd: 13:00"
            onChange={(e) => setTrimEnd(e.target.value)} />
        </label>

        <label>Loại clip
          <select className="pb-select" value={clipType}
            onChange={(e) => setClipType(e.target.value as ClipType)}>
            <option value="training">{CLIP_TYPE_LABEL.training}</option>
            <option value="match_points">{CLIP_TYPE_LABEL.match_points}</option>
          </select>
        </label>

        <label>Model AI
          <select className="pb-select" value={model || defaultModel}
            onChange={(e) => setModel(e.target.value)}>
            {models.map((m) => (
              <option key={m} value={m}>{m}{m === defaultModel ? " (mặc định)" : ""}</option>
            ))}
          </select>
        </label>

        <label>Tôi đứng ở đâu trong khung?
          <select className="pb-select" value={meSide}
            onChange={(e) => setMeSide(e.target.value as Side)}>
            {SIDE_ORDER.map((s) => (
              <option key={s} value={s}>{SIDE_LABEL[s]}</option>
            ))}
          </select>
        </label>

        <label>Ngoại hình (áo màu…)
          <input className="pb-input" value={meAppearance} placeholder="vd: áo đỏ, quần đen"
            onChange={(e) => setMeAppearance(e.target.value)} />
        </label>

        <label className="va-col-span">Tiêu đề
          <input className="pb-input" value={title} placeholder="vd: Tập giao bóng 20/6"
            onChange={(e) => setTitle(e.target.value)} />
        </label>

        <label className="va-col-span">Ghi chú (tùy chọn)
          <input className="pb-input" value={note}
            onChange={(e) => setNote(e.target.value)} />
        </label>
      </div>

      <p className="va-muted">
        Dán/chọn file video trên máy. Nhập 2 ô thời gian để cắt đúng đoạn cần phân tích
        (chỉ đoạn cắt được lưu làm tư liệu, file gốc giữ nguyên). Với clip trận đấu, khai
        “Tôi đứng ở đâu” + màu áo giúp model nhận đúng bạn và tự tích lũy ảnh nhận diện cho
        các clip sau.
      </p>

      {health && !health.ollama_up && <div className="pb-error">{health.message}</div>}
      {health && health.ollama_up && !health.default_available && (
        <div className="pb-error">{health.message}</div>
      )}

      <button className="btn primary va-mt" disabled={!hasSource || uploading} onClick={submit}>
        {uploading ? "Đang xử lý…" : "Cắt & phân tích"}
      </button>
    </section>
  );
}
