import { useCallback, useEffect, useState } from "react";
import { headCoachApi } from "./api";
import { useLoad, useMutate } from "../../shared/useApi";
import CoachChat from "./components/CoachChat";
import CoachNotes from "./components/CoachNotes";
import DevLogs from "./components/DevLogs";
import { fmtTime } from "./fmt";
import type { Assessment, Directive, DirectiveProgress, NotesOut } from "./types";

const AREA: Record<string, { icon: string; label: string }> = {
  training: { icon: "💪", label: "Thể lực" },
  playing_hours: { icon: "⏱️", label: "Giờ đánh" },
  matches: { icon: "🏓", label: "Thi đấu" },
  skill: { icon: "🎯", label: "Kỹ năng" },
  tactics: { icon: "♟️", label: "Chiến thuật" },
  recovery: { icon: "🛌", label: "Hồi phục" },
  // Aliases the model sometimes emits instead of the canonical areas —
  // mapped so the card never shows a raw English key.
  playing: { icon: "⏱️", label: "Giờ đánh" },
  training_hours: { icon: "⏱️", label: "Giờ tập" },
  physical_training: { icon: "💪", label: "Thể lực" },
};

function areaOf(d: Directive) {
  return AREA[d.area] ?? { icon: "📌", label: d.area };
}

// What each trackable metric actually measures (mirrors backend _week_actual)
// — shown next to the progress bar so the order text can't be misread.
const METRIC_SCOPE: Record<string, string> = {
  physical_sessions_per_week: "buổi thể lực Training Center",
  racket_hours_per_week: "tổng cầm vợt: tập + thi đấu",
  coach_hours_per_week: "chỉ tính giờ với HLV",
  matches_per_week: "mọi trận, cả đơn lẫn đôi",
  singles_matches_per_week: "chỉ trận đơn",
  doubles_matches_per_week: "chỉ trận đôi",
  matches_vs_pips_per_week: "trận gặp đối thủ gai",
};

export default function HeadCoach() {
  const [generating, setGenerating] = useState(false);
  const {
    data,
    error: loadError,
    loading,
    reload,
  } = useLoad<Assessment>(() => headCoachApi.getAssessment(), []);
  const { run, error: mutateError, clearError } = useMutate();
  const error = mutateError ?? loadError;

  // Live weekly progress for trackable directives (re-fetched when a new
  // verdict arrives, since the deps include the assessment id).
  const { data: progress } = useLoad(
    () => headCoachApi.getDirectiveProgress(),
    [data?.id]
  );
  const progressByIndex = new Map<number, DirectiveProgress>(
    (progress?.items ?? []).map((p) => [p.index, p])
  );

  // The coach's notebook — refreshed after each chat reply (the coach may
  // have auto-written notes) and edited from the notes panel.
  const {
    data: notesData,
    reload: reloadNotes,
    setData: setNotesData,
  } = useLoad<NotesOut>(() => headCoachApi.getNotes(), []);
  const { run: runNotes, busy: notesBusy, error: notesError } = useMutate();
  const addNote = useCallback(
    async (text: string) => {
      const out = await runNotes(() => headCoachApi.addNote(text));
      if (out !== undefined) setNotesData(out);
      return out !== undefined; // tells the input whether to clear
    },
    [runNotes, setNotesData]
  );
  const deleteNote = useCallback(
    async (id: number) => {
      const out = await runNotes(() => headCoachApi.deleteNote(id));
      if (out !== undefined) setNotesData(out);
    },
    [runNotes, setNotesData]
  );

  // On mount, resume the "generating" state if a run is already in flight
  // (e.g. the tab was switched away and back while the local model worked).
  useEffect(() => {
    let alive = true;
    headCoachApi
      .getStatus()
      .then((s) => {
        if (alive && s.status === "generating") setGenerating(true);
      })
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);

  // While generating, poll the status every 3s; when the run finishes, stop
  // and refetch the completed assessment (or surface the error). A rejected
  // poll (dev-server reload, one dropped request) is transient — keep
  // polling; only a *returned* error status is terminal.
  useEffect(() => {
    if (!generating) return;
    const timer = setInterval(async () => {
      let s;
      try {
        s = await headCoachApi.getStatus();
      } catch {
        return; // transient fetch failure — try again next tick
      }
      if (s.status === "generating") return;
      setGenerating(false);
      if (s.status === "error") {
        const msg = s.error_msg || "Phân tích thất bại.";
        void run(() => Promise.reject(new Error(msg))); // surface via shared error state
        return;
      }
      reload();
    }, 3000);
    return () => clearInterval(timer);
  }, [generating, reload, run]);

  const generate = async () => {
    clearError();
    const started = await run(() => headCoachApi.generate());
    if (started !== undefined) setGenerating(true);
  };

  const m = data?.sources.match ?? {};
  const detail = data?.sources.match_detail ?? {};
  const training = data?.sources.training ?? {};
  const notes = data?.sources.notes ?? [];

  return (
    <div className="hc">
      <div className="hc-main">
      <div className="hc-top">
        <div>
          <h2 className="hc-title">🧠 HLV trưởng</h2>
          <p className="hc-sub">
            Huấn luyện viên cá nhân — tổng hợp toàn bộ số liệu của bạn và đưa ra
            đánh giá nghiêm khắc + kế hoạch.
          </p>
        </div>
        <button className="btn primary" onClick={generate} disabled={generating}>
          {generating ? "⏳ Đang phân tích…" : data?.empty ? "Phân tích lần đầu" : "Phân tích lại"}
        </button>
      </div>

      {generating && (
        <div className="hc-note">
          HLV đang xem lại số liệu của bạn (chạy model cục bộ ở chế độ nền —
          có thể chuyển tab khác rồi quay lại, kết quả sẽ tự hiện)…
        </div>
      )}
      {error && <div className="hc-error">⚠️ {error}</div>}

      {!loading && data?.empty && !generating && (
        <div className="hc-empty">
          Chưa có buổi đánh giá nào. Bấm <b>“Phân tích lần đầu”</b> để HLV trưởng
          đọc hồ sơ kỹ thuật, thể lực, kết quả thi đấu và chiến thuật của bạn.
        </div>
      )}

      {data && !data.empty && (
        <>
          <section className="hc-overall">
            <h3>Đánh giá tổng quan</h3>
            <p>{data.overall_assessment}</p>
          </section>

          {data.directives.length > 0 && (
            <section className="hc-section">
              <h3>📋 Mệnh lệnh tăng cường</h3>
              <div className="hc-directives">
                {data.directives.map((d, i) => {
                  const a = areaOf(d);
                  const p = progressByIndex.get(i);
                  return (
                    <div key={i} className="hc-directive">
                      <div className="hc-directive-head">
                        <span className="hc-area">{a.icon} {a.label}</span>
                        {d.target && <span className="hc-target">{d.target}</span>}
                      </div>
                      <div className="hc-order">{d.order}</div>
                      {d.reason && <div className="hc-reason">↳ {d.reason}</div>}
                      {p && (
                        <div
                          className="hc-progress"
                          title="Tiến độ tuần này, tính tự động từ dữ liệu đã ghi (Thứ 2 → hôm nay)"
                        >
                          <div className="hc-progress-track">
                            <div
                              className={`hc-progress-fill${p.pct >= 100 ? " done" : ""}`}
                              style={{ width: `${p.pct}%` }}
                            />
                          </div>
                          <span className="hc-progress-label">
                            Tuần này: <b>{p.actual}</b>/{p.value} {p.unit_vi}
                            {p.pct >= 100 ? " ✓" : ""}
                            {METRIC_SCOPE[p.metric] && (
                              <span className="hc-progress-scope">
                                {" "}· {METRIC_SCOPE[p.metric]}
                              </span>
                            )}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          {data.top_priorities.length > 0 && (
            <section className="hc-section">
              <h3>🎯 Ưu tiên</h3>
              <ol className="hc-priorities">
                {data.top_priorities.map((p, i) => (
                  <li key={i}>
                    <div className="hc-pri-title">{p.title}</div>
                    {p.why && <div className="hc-pri-why">{p.why}</div>}
                    {p.source && <span className="hc-chip">{p.source}</span>}
                  </li>
                ))}
              </ol>
            </section>
          )}

          {data.week_plan.length > 0 && (
            <section className="hc-section">
              <h3>🗓️ Kế hoạch tuần</h3>
              <div className="hc-week">
                {data.week_plan.map((d, i) => (
                  <div key={i} className="hc-day">
                    <div className="hc-day-name">{d.day}</div>
                    <div className="hc-day-focus">{d.focus}</div>
                    <div className="hc-day-detail">{d.detail}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {data.watch_items.length > 0 && (
            <section className="hc-section hc-watch">
              <h3>⚠️ Cần lưu ý</h3>
              <ul>
                {data.watch_items.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </section>
          )}

          <details className="hc-sources">
            <summary>📊 Nguồn dữ liệu HLV đã đọc</summary>
            <div className="hc-source-grid">
              <div>Khoảng thời gian: {data.sources.generated_for_range}</div>
              <div>
                Thi đấu (90 ngày): đơn {m.singles?.played ?? "—"} trận · đôi{" "}
                {m.doubles?.played ?? "—"} · gai {m.vs_pips?.played ?? "—"} · tổng{" "}
                {m.overall?.played ?? "—"}
              </div>
              <div>
                Phân tích sâu ({detail.window ?? "—"}): trận tập{" "}
                {detail.practice?.played ?? "—"} · trận giải{" "}
                {detail.official?.played ?? "—"} · head-to-head{" "}
                {detail.top_h2h?.length ?? 0} đối thủ
              </div>
              <div>
                Thể lực: cấp {training.level ?? "—"} ·{" "}
                {training.sessions_last_7d ?? 0} buổi/7 ngày · Ghi chú:{" "}
                {notes.length} ngày gần nhất
              </div>
            </div>
          </details>

          <div className="hc-meta">
            Tạo lúc {fmtTime(data.created_at)} · model {data.model}
          </div>
        </>
      )}
      <DevLogs />
      </div>

      <aside className="hc-side">
        <section className="hc-side-block">
          <h3>💬 Trao đổi với HLV</h3>
          <p className="hc-hint">
            Đặt mục tiêu ngắn hạn, báo lịch bận, hỏi về số liệu — HLV trả lời
            dựa trên dữ liệu thật và nhớ mọi trao đổi (lưu trong database).
          </p>
          <CoachChat onCoachReply={reloadNotes} />
        </section>
        <section className="hc-side-block">
          <h3>📒 Sổ tay HLV</h3>
          <p className="hc-hint">
            Điều đã chốt — được đưa vào mọi câu trả lời và cả bản phân tích.
          </p>
          <CoachNotes
            notes={notesData?.notes ?? []}
            onAdd={addNote}
            onDelete={deleteNote}
            busy={notesBusy}
            error={notesError}
          />
        </section>
      </aside>
    </div>
  );
}
