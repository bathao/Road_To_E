import { useCallback, useEffect, useState } from "react";
import { headCoachApi } from "./api";
import type { Assessment, Directive } from "./types";

const AREA: Record<string, { icon: string; label: string }> = {
  training: { icon: "💪", label: "Thể lực" },
  playing_hours: { icon: "⏱️", label: "Giờ đánh" },
  matches: { icon: "🏓", label: "Thi đấu" },
  skill: { icon: "🎯", label: "Kỹ năng" },
  tactics: { icon: "♟️", label: "Chiến thuật" },
  recovery: { icon: "🛌", label: "Hồi phục" },
};

function areaOf(d: Directive) {
  return AREA[d.area] ?? { icon: "📌", label: d.area };
}

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString("vi-VN");
}

export default function HeadCoach() {
  const [data, setData] = useState<Assessment | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await headCoachApi.getAssessment());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      setData(await headCoachApi.generate());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setGenerating(false);
    }
  };

  const m = (data?.sources.match ?? {}) as Record<string, any>;

  return (
    <div className="hc">
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
          HLV đang xem lại số liệu của bạn (chạy model cục bộ, ~30–60 giây)…
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
                  return (
                    <div key={i} className="hc-directive">
                      <div className="hc-directive-head">
                        <span className="hc-area">{a.icon} {a.label}</span>
                        {d.target && <span className="hc-target">{d.target}</span>}
                      </div>
                      <div className="hc-order">{d.order}</div>
                      {d.reason && <div className="hc-reason">↳ {d.reason}</div>}
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

          {data.tactics.length > 0 && (
            <section className="hc-section">
              <h3>♟️ Chiến thuật áp dụng trong trận</h3>
              <ul className="hc-tactics">
                {data.tactics.map((t, i) => (
                  <li key={i}>
                    <span className="hc-situation">{t.situation}</span>
                    <span className="hc-arrow">→</span>
                    <span className="hc-action">{t.action}</span>
                  </li>
                ))}
              </ul>
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
                Thi đấu (90 ngày): đơn {String(m.singles?.played ?? "—")} trận · đôi{" "}
                {String(m.doubles?.played ?? "—")} · gai {String(m.vs_pips?.played ?? "—")} · tổng{" "}
                {String(m.overall?.played ?? "—")}
              </div>
              <div>
                Phân tích video: {String((data.sources.video as any).clips_reviewed ?? 0)} clip ·{" "}
                {String((data.sources.video as any).findings_accepted ?? 0)} nhận xét đã duyệt
              </div>
              <div>
                Thể lực: cấp {String((data.sources.training as any).level ?? "—")} ·{" "}
                {String((data.sources.training as any).sessions_last_7d ?? 0)} buổi/7 ngày
              </div>
            </div>
          </details>

          <div className="hc-meta">
            Tạo lúc {fmtTime(data.created_at)} · model {data.model}
          </div>
        </>
      )}
    </div>
  );
}
