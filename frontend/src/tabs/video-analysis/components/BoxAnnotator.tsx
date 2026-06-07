import { useRef, useState } from "react";

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface Props {
  imageUrl: string;
  saving: boolean;
  onSave: (box: Box) => void | Promise<void>;
  onCancel: () => void;
}

const clamp = (v: number) => Math.max(0, Math.min(1, v));

/** Drag a rectangle over a full frame to mark exactly where the user is. The
 * box is returned normalised (0..1) so it maps to the frame at any size. */
export default function BoxAnnotator({ imageUrl, saving, onSave, onCancel }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const start = useRef<{ x: number; y: number } | null>(null);
  const [box, setBox] = useState<Box | null>(null);

  const norm = (clientX: number, clientY: number) => {
    const r = ref.current!.getBoundingClientRect();
    return { x: clamp((clientX - r.left) / r.width), y: clamp((clientY - r.top) / r.height) };
  };

  const onDown = (e: React.PointerEvent) => {
    e.preventDefault();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    const p = norm(e.clientX, e.clientY);
    start.current = p;
    setBox({ x: p.x, y: p.y, w: 0, h: 0 });
  };

  const onMove = (e: React.PointerEvent) => {
    if (!start.current) return;
    const p = norm(e.clientX, e.clientY);
    const s = start.current;
    setBox({
      x: Math.min(s.x, p.x),
      y: Math.min(s.y, p.y),
      w: Math.abs(p.x - s.x),
      h: Math.abs(p.y - s.y),
    });
  };

  const onUp = () => {
    start.current = null;
  };

  const valid = box && box.w > 0.02 && box.h > 0.02;

  return (
    <div className="va-annot">
      <p className="va-muted">
        Kéo chuột để khoanh ô quanh <b>bạn</b> trong khung hình, rồi lưu — ảnh này được dùng
        làm dữ liệu nhận diện cho các clip sau.
      </p>
      <div
        ref={ref}
        className="va-annot-canvas"
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
      >
        <img src={imageUrl} alt="khung hình" draggable={false} />
        {box && (
          <div
            className="va-annot-box"
            style={{
              left: `${box.x * 100}%`,
              top: `${box.y * 100}%`,
              width: `${box.w * 100}%`,
              height: `${box.h * 100}%`,
            }}
          />
        )}
      </div>
      <div className="va-row-gap va-mt">
        <button
          className="btn primary"
          disabled={!valid || saving}
          onClick={() => valid && onSave(box!)}
        >
          {saving ? "Đang lưu…" : "💾 Lưu vùng này làm ảnh nhận diện"}
        </button>
        <button className="btn" disabled={saving} onClick={onCancel}>Hủy</button>
      </div>
      {!valid && <p className="va-muted">Kéo một ô đủ lớn quanh bạn để bật nút Lưu.</p>}
    </div>
  );
}
