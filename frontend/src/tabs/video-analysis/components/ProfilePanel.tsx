import { useEffect, useState } from "react";
import { videoApi } from "../api";
import type { Profile, ProfileImage, ProfileIn } from "../types";

interface Props {
  profile: Profile;
  images: ProfileImage[];
  onSave: (payload: ProfileIn) => Promise<void>;
  onRegenerate: () => Promise<void>;
  onAddImage: () => Promise<void>;
  onDeleteImage: (id: number) => Promise<void>;
  regenerating: boolean;
  canRegenerate: boolean;
}

const SUMMARY_FIELDS: { key: keyof Profile; label: string }[] = [
  { key: "overall_summary", label: "Tổng quan" },
  { key: "strengths_summary", label: "Điểm mạnh" },
  { key: "weaknesses_summary", label: "Điểm yếu" },
  { key: "serve_summary", label: "Giao bóng" },
  { key: "footwork_summary", label: "Bộ chân" },
  { key: "posture_summary", label: "Tư thế / thân người" },
];

export default function ProfilePanel({
  profile,
  images,
  onSave,
  onRegenerate,
  onAddImage,
  onDeleteImage,
  regenerating,
  canRegenerate,
}: Props) {
  const [draft, setDraft] = useState<Profile>(profile);
  const [editing, setEditing] = useState(false);
  const [addingImage, setAddingImage] = useState(false);

  useEffect(() => {
    setDraft(profile);
  }, [profile]);

  const set = (patch: Partial<Profile>) => setDraft((d) => ({ ...d, ...patch }));

  const addImage = async () => {
    setAddingImage(true);
    try {
      await onAddImage();
    } finally {
      setAddingImage(false);
    }
  };

  const save = async () => {
    await onSave({
      name: draft.name,
      handed: draft.handed,
      grip: draft.grip,
      style: draft.style,
      equipment: draft.equipment,
      physique: draft.physique,
    });
    setEditing(false);
  };

  return (
    <section className="va-card va-profile">
      <div className="va-card-head">
        <h3>👤 Hồ sơ: {profile.name}</h3>
        {editing ? (
          <div className="va-row-gap">
            <button className="btn" onClick={() => { setDraft(profile); setEditing(false); }}>
              Hủy
            </button>
            <button className="btn primary" onClick={save}>Lưu</button>
          </div>
        ) : (
          <button className="btn" onClick={() => setEditing(true)}>Sửa</button>
        )}
      </div>

      {editing ? (
        <div className="va-form-grid">
          <label>Tên<input className="pb-input" value={draft.name}
            onChange={(e) => set({ name: e.target.value })} /></label>
          <label>Thuận tay
            <select className="pb-select" value={draft.handed}
              onChange={(e) => set({ handed: e.target.value })}>
              <option value="right">Phải</option>
              <option value="left">Trái</option>
            </select>
          </label>
          <label>Cầm vợt
            <select className="pb-select" value={draft.grip}
              onChange={(e) => set({ grip: e.target.value })}>
              <option value="shakehand">Ngang (shakehand)</option>
              <option value="penhold">Dọc (penhold)</option>
            </select>
          </label>
          <label>Lối đánh<input className="pb-input" value={draft.style}
            placeholder="công, phòng thủ, toàn diện…"
            onChange={(e) => set({ style: e.target.value })} /></label>
          <label className="va-col-span">Dụng cụ (cốt + mặt)<input className="pb-input"
            value={draft.equipment} onChange={(e) => set({ equipment: e.target.value })} /></label>
          <label className="va-col-span">Thể hình (chiều cao / vóc dáng)<input className="pb-input"
            value={draft.physique} onChange={(e) => set({ physique: e.target.value })} /></label>
        </div>
      ) : (
        <div className="va-basics">
          <span className="va-chip">Thuận tay: {draft.handed === "left" ? "Trái" : "Phải"}</span>
          <span className="va-chip">Vợt: {draft.grip === "penhold" ? "Dọc" : "Ngang"}</span>
          {draft.style && <span className="va-chip">Lối đánh: {draft.style}</span>}
          {draft.equipment && <span className="va-chip">Dụng cụ: {draft.equipment}</span>}
          {draft.physique && <span className="va-chip">Thể hình: {draft.physique}</span>}
        </div>
      )}

      <div className="va-card-head va-mt">
        <h4>Ảnh nhận diện ({images.length})</h4>
        <button className="btn" disabled={addingImage} onClick={addImage}>
          {addingImage ? "Đang mở…" : "📁 Thêm ảnh"}
        </button>
      </div>
      <p className="va-muted">
        Ảnh để model tự nhận ra bạn trong clip. Tự tăng dần từ các clip bạn đã khai vị trí;
        có thể thêm tay ảnh chân dung rõ mặt.
      </p>
      {images.length > 0 ? (
        <div className="va-ref-grid">
          {images.map((img) => (
            <div key={img.id} className="va-ref-item">
              <img src={videoApi.profileImageUrl(img.id)} alt="ref" />
              <button className="va-x va-ref-x" title="Xóa" onClick={() => onDeleteImage(img.id)}>×</button>
            </div>
          ))}
        </div>
      ) : (
        <p className="va-muted">Chưa có ảnh nhận diện nào.</p>
      )}

      <div className="va-card-head va-mt">
        <h4>Hồ sơ tổng hợp (AI)</h4>
        <button
          className="btn"
          disabled={regenerating || !canRegenerate}
          title={canRegenerate ? "" : "Cần có nhận xét (phân tích ít nhất 1 clip) trước khi tổng hợp"}
          onClick={onRegenerate}
        >
          {regenerating ? "Đang tổng hợp…" : "↻ Tổng hợp lại từ nhận xét"}
        </button>
      </div>
      {!canRegenerate && (
        <p className="va-muted">
          Chưa có nhận xét nào để tổng hợp. Hãy phân tích ít nhất 1 clip, hoặc thêm
          nhận xét tay ở mục bên dưới.
        </p>
      )}
      <div className="va-summaries">
        {SUMMARY_FIELDS.map(({ key, label }) => {
          const value = (profile[key] as string) || "";
          return (
            <div key={key} className="va-summary-item">
              <div className="va-summary-label">{label}</div>
              <div className={`va-summary-text${value ? "" : " va-muted"}`}>
                {value || "— chưa có —"}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
