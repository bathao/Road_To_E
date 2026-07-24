// Collapsed dev panel: recent backend log lines + Ollama VRAM occupancy.
// For diagnosing a failed/slow generation (OOM, model fallback, retries,
// another model hogging the GPU). Fetches only while open; auto-refreshes
// every 3s so a running generation can be watched live.
import { useEffect, useRef, useState } from "react";
import { headCoachApi } from "../api";
import type { DebugOut } from "../types";

export default function DevLogs() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<DebugOut | null>(null);
  const preRef = useRef<HTMLPreElement>(null);
  // True while the user is (near) the bottom of the log pane. Scrolling up to
  // read older lines must not be undone by the 3s refresh.
  const stickBottom = useRef(true);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    const load = async () => {
      try {
        const d = await headCoachApi.getDebug();
        if (alive) setData(d);
      } catch {
        // backend unreachable — keep the last snapshot
      }
    };
    void load();
    const timer = setInterval(load, 3000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [open]);

  // Keep the newest lines in view — only while the user hasn't scrolled up.
  useEffect(() => {
    const el = preRef.current;
    if (el && stickBottom.current) el.scrollTop = el.scrollHeight;
  }, [data?.logs]);

  return (
    <details
      className="hc-devlogs"
      onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}
    >
      <summary>🛠️ Log kỹ thuật (dev)</summary>
      {data && (
        <div className="hc-devlogs-body">
          <div className="hc-devlogs-gpu">
            {data.ollama_ok ? (
              data.loaded_models.length ? (
                <>
                  Ollama đang giữ trong VRAM:{" "}
                  {data.loaded_models.map((m) => (
                    <span key={m.name} className="hc-chip">
                      {m.name} · {(m.size_vram_mb / 1024).toFixed(1)} GB GPU
                      {m.size_mb > m.size_vram_mb
                        ? ` (+${((m.size_mb - m.size_vram_mb) / 1024).toFixed(1)} GB RAM)`
                        : ""}
                    </span>
                  ))}
                </>
              ) : (
                <span>Ollama chạy, chưa load model nào (VRAM trống).</span>
              )
            ) : (
              <span className="hc-devlogs-err">
                Không kết nối được Ollama: {data.ollama_error}
              </span>
            )}
          </div>
          <pre
            ref={preRef}
            className="hc-devlogs-pre"
            onScroll={() => {
              const el = preRef.current;
              if (el) {
                stickBottom.current =
                  el.scrollHeight - el.scrollTop - el.clientHeight < 20;
              }
            }}
          >
            {data.logs.length ? data.logs.join("\n") : "(chưa có log nào từ khi server khởi động)"}
          </pre>
        </div>
      )}
    </details>
  );
}
