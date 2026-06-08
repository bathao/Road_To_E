import { useEffect, useState } from "react";

interface Props {
  status: "processing" | "analyzing";
  startedAt: string | null;
}

// Rough expected durations (seconds). The VLM call is opaque so we can't report
// true progress — the bar fills toward this estimate and caps below 100% until
// the job actually finishes, while the timer counts real elapsed time.
const ESTIMATE_SEC: Record<string, number> = {
  processing: 30, // step 1: detect (fewer frames)
  analyzing: 105, // step 2: deep analysis (14 frames + pose)
};

const LABEL: Record<string, string> = {
  processing: "Bước 1: đang nhận diện bạn trong clip…",
  analyzing: "Bước 2: đang phân tích chuyên sâu…",
};

function mmss(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  return `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;
}

export default function AnalysisProgress({ status, startedAt }: Props) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  // Elapsed is derived from the server start time, so it survives re-renders
  // and page reloads (no client-side accumulation).
  const start = startedAt ? Date.parse(startedAt) : now;
  const elapsed = Math.max(0, (now - start) / 1000);
  const est = ESTIMATE_SEC[status] ?? 60;
  const over = elapsed >= est;
  const frac = over ? 0.95 : Math.max(0.04, elapsed / est);

  return (
    <div className="va-progress">
      <p className="va-muted">⏳ {LABEL[status] ?? "Đang xử lý…"}</p>
      <div className="va-progbar">
        <div
          className={`va-progbar-fill${over ? " over" : ""}`}
          style={{ width: `${Math.round(frac * 100)}%` }}
        />
      </div>
      <p className="va-muted va-prog-meta">
        Đã chạy <b>{mmss(elapsed)}</b>
        {over ? " · lâu hơn dự kiến, sắp xong…" : ` · ước tính ~${mmss(est)}`}
      </p>
    </div>
  );
}
