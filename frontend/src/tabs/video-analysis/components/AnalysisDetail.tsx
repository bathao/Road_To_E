import { useEffect, useMemo, useRef, useState } from "react";
import { videoApi } from "../api";
import type {
  Aspect,
  BallTracking,
  ClipDetail,
  FindingDecision,
  MetricTrend,
  Polarity,
  Side,
  Trait,
} from "../types";
import {
  ASPECT_LABEL,
  ASPECT_ORDER,
  CLIP_TYPE_LABEL,
  FOCUS_LABEL,
  SIDE_LABEL,
  SIDE_ORDER,
  STATUS_LABEL,
} from "../labels";
import BoxAnnotator, { type Box } from "./BoxAnnotator";
import AnalysisProgress from "./AnalysisProgress";

interface Props {
  detail: ClipDetail;
  videoUrl: string;
  previewUrl: string;
  frameUrl: string;
  reanalyzing: boolean;
  identifying: boolean;
  cropping: boolean;
  reviewing: boolean;
  stopping: boolean;
  onReanalyze: () => void;
  onIdentify: (side: Side, appearance: string) => void;
  onConfirm: () => void;
  onCropReference: (box: Box) => Promise<boolean>;
  onReview: (decisions: FindingDecision[]) => Promise<void>;
  onStop: () => void;
  onDelete: () => void;
}

// Local editable state for one finding under review.
interface Draft {
  accept: boolean;
  text: string;
  aspect: Aspect;
  polarity: Polarity;
}

type Metric = { mean: number; min: number; max: number } | null | undefined;

function metricText(m: Metric, unit = ""): string {
  if (!m) return "—";
  return `${m.mean}${unit} (${m.min}–${m.max}${unit})`;
}

function fmtTime(s: number): string {
  const x = Math.max(0, Math.floor(s));
  return `${Math.floor(x / 60)}:${(x % 60).toString().padStart(2, "0")}`;
}

// A clickable evidence chip: jumps the clip video to the moment the finding was
// observed (t_ref, seconds) and shows the model's confidence.
function TimeChip({ t, conf, onSeek }: {
  t: number | null;
  conf: number | null;
  onSeek: (t: number) => void;
}) {
  if (t == null || t <= 0) return null;
  return (
    <button type="button" className="va-tref" onClick={() => onSeek(t)}
      title="Nhảy tới khoảnh khắc này trong clip">
      ▶ {fmtTime(t)}{conf != null ? ` · ${Math.round(conf * 100)}%` : ""}
    </button>
  );
}

// A 3×3 placement heat-grid of where the ball landed on the table (best-effort).
// gx 0..2 = left/center/right, gy 0..2 = near-net/mid/far-end.
function PlacementGrid({ ball }: { ball: BallTracking }) {
  const zones = ball.zones ?? [];
  if (!zones.length) return null;
  const max = Math.max(...zones.map((z) => z.count), 1);
  const count = (gx: number, gy: number) =>
    zones.find((z) => z.gx === gx && z.gy === gy)?.count ?? 0;
  return (
    <div className="va-placement">
      {[0, 1, 2].map((gy) =>
        [0, 1, 2].map((gx) => {
          const n = count(gx, gy);
          return (
            <div key={`${gx}-${gy}`} className="va-placement-cell"
              style={{ background: `rgba(74,144,217,${n ? 0.15 + 0.65 * (n / max) : 0.04})` }}>
              {n || ""}
            </div>
          );
        })
      )}
    </div>
  );
}

// A coloured delta chip for a metric vs the player's own baseline.
function TrendChip({ t }: { t: MetricTrend }) {
  const cls =
    t.trend === "improved" ? "va-trend-up"
    : t.trend === "declined" ? "va-trend-down" : "va-trend-flat";
  const arrow = t.delta > 0 ? "▲" : t.delta < 0 ? "▼" : "■";
  const word =
    t.trend === "improved" ? "tốt hơn"
    : t.trend === "declined" ? "kém hơn"
    : t.trend === "flat" ? "≈ như cũ" : "thay đổi";
  const amt = t.pct != null
    ? `${t.pct > 0 ? "+" : ""}${t.pct}%`
    : `${t.delta > 0 ? "+" : ""}${t.delta}`;
  return <span className={`va-trend ${cls}`}>{arrow} {amt} · {word}</span>;
}

// The annotated evidence frame (pose skeleton + joint angles) for a finding.
// Clicking it seeks the clip to that moment, like the time chip.
function EvidenceThumb({ clipId, trait, onSeek }: {
  clipId: number;
  trait: Trait;
  onSeek: (t: number) => void;
}) {
  const ev = trait.evidence;
  if (!ev?.thumb) return null;
  return (
    <img
      className="va-evidence"
      src={videoApi.evidenceUrl(clipId, ev.thumb)}
      alt="bằng chứng (khung xương + góc khớp)"
      title="Bằng chứng tại khoảnh khắc này — bấm để xem trong clip"
      onClick={() => ev.t != null && onSeek(ev.t)}
      onError={(e) => ((e.target as HTMLImageElement).style.display = "none")}
    />
  );
}

export default function AnalysisDetail({
  detail,
  videoUrl,
  previewUrl,
  frameUrl,
  reanalyzing,
  identifying,
  cropping,
  reviewing,
  stopping,
  onReanalyze,
  onIdentify,
  onConfirm,
  onCropReference,
  onReview,
  onStop,
  onDelete,
}: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const seekTo = (t: number) => {
    const v = videoRef.current;
    if (!v) return;
    v.currentTime = t;
    v.play().catch(() => {});
    v.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  const [side, setSide] = useState<Side>(detail.me_side || "");
  const [appearance, setAppearance] = useState(detail.me_appearance || "");
  const [correcting, setCorrecting] = useState(false);
  const [annotating, setAnnotating] = useState(false);
  const [savedNote, setSavedNote] = useState(false);

  // ---- findings review state ----
  const [drafts, setDrafts] = useState<Record<number, Draft>>({});
  const [reEditing, setReEditing] = useState(false);
  const reviewed = detail.reviewed_at != null;

  useEffect(() => {
    const init: Record<number, Draft> = {};
    for (const t of detail.traits) {
      init[t.id] = {
        accept: t.status !== "rejected",
        text: t.text,
        aspect: t.aspect,
        polarity: t.polarity,
      };
    }
    setDrafts(init);
    setReEditing(false);
  }, [detail.id, detail.reviewed_at, detail.analysis?.created_at]);

  const setDraft = (id: number, patch: Partial<Draft>) =>
    setDrafts((d) => ({ ...d, [id]: { ...d[id], ...patch } }));

  const acceptedCount = useMemo(
    () => Object.values(drafts).filter((d) => d.accept).length,
    [drafts]
  );

  const submitReview = async () => {
    const decisions: FindingDecision[] = detail.traits.map((t) => {
      const d = drafts[t.id];
      return {
        id: t.id,
        accept: d?.accept ?? true,
        text: d?.text,
        aspect: d?.aspect,
        polarity: d?.polarity,
      };
    });
    await onReview(decisions);
    setReEditing(false);
  };

  const toggleAnnotator = () => {
    setSavedNote(false);
    setAnnotating((v) => !v);
  };

  const saveBox = async (box: Box) => {
    const ok = await onCropReference(box);
    if (ok) {
      setAnnotating(false);
      setSavedNote(true);
    }
  };
  const a = detail.analysis;
  const raw = a?.raw;
  const pose = (a?.pose ?? {}) as Record<string, any>;
  const poseAvailable = pose.available && pose.frames_with_pose > 0;

  const showEditor = detail.status === "done" && (!reviewed || reEditing);
  const acceptedTraits = detail.traits.filter((t) => t.status === "accepted");

  return (
    <section className="va-card va-detail">
      <div className="va-card-head">
        <h3>{detail.title || detail.original_name}</h3>
        <div className="va-row-gap">
          <button className="btn" disabled={reanalyzing} onClick={onReanalyze}>
            {reanalyzing ? "Đang phân tích…" : "↻ Phân tích lại"}
          </button>
          <button className="btn danger" onClick={onDelete}>Xóa</button>
        </div>
      </div>

      <div className="va-detail-grid">
        <div className="va-video-wrap">
          <video ref={videoRef} src={videoUrl} controls className="va-video" />
          <div className="va-muted va-video-meta">
            {CLIP_TYPE_LABEL[detail.clip_type]}
            {detail.focus ? ` · 🎯 ${FOCUS_LABEL[detail.focus]}` : ""}
            {detail.fps ? ` · ${detail.fps} fps` : ""}
            {detail.frames_sampled ? ` · ${detail.frames_sampled} khung phân tích` : ""}
            {detail.model ? ` · ${detail.model}` : ""}
          </div>
        </div>

        <div className="va-analysis">
          {(detail.status === "processing" || detail.status === "analyzing") && (
            <>
              <AnalysisProgress status={detail.status} startedAt={detail.processing_started_at} />
              <button className="btn danger va-stop-btn" disabled={stopping} onClick={onStop}>
                {stopping ? "Đang dừng…" : "■ Dừng"}
              </button>
            </>
          )}
          {detail.status === "stopped" && (
            <p className="va-muted">
              ■ Đã dừng. Bấm <b>↻ Phân tích lại</b> ở trên để chạy lại.
            </p>
          )}
          {detail.status === "error" && (
            <div className="pb-error">Lỗi: {detail.error_msg}</div>
          )}
          {detail.status === "pending" && (
            <p className="va-muted">{STATUS_LABEL.pending}</p>
          )}

          {detail.subject_desc && detail.status !== "needs_id" && (
            <p className={`va-subject${detail.identified ? "" : " va-subject-warn"}`}>
              {detail.identified ? "🎯 Model nhận diện bạn là: " : "❓ Model đoán: "}
              {detail.subject_desc}
            </p>
          )}

          {/* Step-1 result → confirm before deep analysis */}
          {detail.status === "awaiting_confirm" && (
            <div className="va-confirm">
              <h4>Đây có phải là bạn không?</h4>
              <div className="va-confirm-body">
                <img className="va-preview" src={previewUrl} alt="người được nhận diện"
                  onError={(e) => ((e.target as HTMLImageElement).style.display = "none")} />
                <div>
                  <p className="va-muted">
                    Model cho rằng bạn ở <b>{SIDE_LABEL[detail.me_side] ?? detail.me_side}</b>
                    {detail.me_appearance ? <>, <b>{detail.me_appearance}</b></> : null}. Xác nhận
                    để bắt đầu phân tích chuyên sâu; ảnh này sẽ được lưu giúp nhận đúng lần sau.
                  </p>
                  <div className="va-row-gap">
                    <button className="btn primary" disabled={identifying} onClick={onConfirm}>
                      {identifying ? "…" : "✓ Đúng là tôi — phân tích"}
                    </button>
                    <button className="btn" onClick={() => setCorrecting((v) => !v)}>
                      ✗ Không đúng — sửa
                    </button>
                    <button className="btn" onClick={toggleAnnotator}>
                      ✏️ Khoanh vùng là tôi
                    </button>
                  </div>
                  {savedNote && (
                    <p className="va-saved-note">✓ Đã lưu vào ảnh nhận diện (xem cột Hồ sơ bên trái).</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Ask / correct identity form */}
          {(detail.status === "needs_id" || (detail.status === "awaiting_confirm" && correcting)) && (
            <div className="va-needs-id">
              {detail.status === "needs_id" && <h4>❓ Model chưa nhận ra bạn</h4>}
              <p className="va-muted">
                Cho biết bạn ở đâu / mặc gì trong clip này. Sau khi xác nhận, ảnh của bạn được
                lưu để các lần sau nhận đúng hơn.
              </p>
              <div className="va-needs-id-row">
                <select className="pb-select" value={side}
                  onChange={(e) => setSide(e.target.value as Side)}>
                  {SIDE_ORDER.map((s) => (
                    <option key={s} value={s}>{SIDE_LABEL[s]}</option>
                  ))}
                </select>
                <input className="pb-input" value={appearance} placeholder="áo màu… (tùy chọn)"
                  onChange={(e) => setAppearance(e.target.value)} />
                <button className="btn primary" disabled={identifying || !side}
                  onClick={() => onIdentify(side, appearance)}>
                  {identifying ? "Đang xử lý…" : "Xác nhận & phân tích"}
                </button>
              </div>
              <button className="btn va-mt" onClick={toggleAnnotator}>
                ✏️ Hoặc khoanh vùng là tôi trên khung hình
              </button>
            </div>
          )}

          {annotating &&
            (detail.status === "awaiting_confirm" || detail.status === "needs_id") && (
              <BoxAnnotator
                imageUrl={frameUrl}
                saving={cropping}
                onSave={saveBox}
                onCancel={() => setAnnotating(false)}
              />
            )}

          {a && raw && detail.status === "done" && (
            <>
              {raw.summary && <p className="va-summary-block">{raw.summary}</p>}

              {raw.critique && (raw.critique.dropped > 0 || raw.critique.downgraded > 0) && (
                <p className="va-muted va-critique-note">
                  🔍 AI tự kiểm tra lại {raw.critique.reviewed} nhận xét:
                  {raw.critique.dropped > 0 ? ` loại ${raw.critique.dropped} ý thiếu căn cứ` : ""}
                  {raw.critique.dropped > 0 && raw.critique.downgraded > 0 ? "," : ""}
                  {raw.critique.downgraded > 0 ? ` hạ độ tin cậy ${raw.critique.downgraded} ý chưa chắc` : ""}.
                </p>
              )}

              {/* ---- Findings review gate ---- */}
              {showEditor ? (
                <div className="va-review">
                  <div className="va-card-head">
                    <h4>📝 Duyệt nhận xét trước khi lưu vào hồ sơ</h4>
                    <span className="va-muted">{acceptedCount}/{detail.traits.length} giữ lại</span>
                  </div>
                  <p className="va-muted">
                    Bỏ tick ý nào sai, sửa chữ nếu cần, rồi bấm Duyệt. Chỉ các nhận xét được
                    giữ mới tính vào hồ sơ kỹ năng.
                  </p>
                  {detail.traits.length === 0 ? (
                    <p className="va-muted">Phân tích này không rút ra nhận xét nào.</p>
                  ) : (
                    <ul className="va-review-list">
                      {detail.traits.map((t) => {
                        const d = drafts[t.id];
                        if (!d) return null;
                        return (
                          <li key={t.id} className={`va-review-item va-${d.polarity}`}>
                            <input
                              type="checkbox"
                              checked={d.accept}
                              onChange={(e) => setDraft(t.id, { accept: e.target.checked })}
                            />
                            <select
                              className="pb-select va-review-aspect"
                              value={d.aspect}
                              onChange={(e) => setDraft(t.id, { aspect: e.target.value as Aspect })}
                            >
                              {ASPECT_ORDER.map((asp) => (
                                <option key={asp} value={asp}>{ASPECT_LABEL[asp]}</option>
                              ))}
                            </select>
                            <select
                              className="pb-select va-review-pol"
                              value={d.polarity}
                              onChange={(e) => setDraft(t.id, { polarity: e.target.value as Polarity })}
                            >
                              <option value="strength">✅ Mạnh</option>
                              <option value="weakness">⚠️ Yếu</option>
                            </select>
                            <input
                              className="pb-input va-review-text"
                              value={d.text}
                              onChange={(e) => setDraft(t.id, { text: e.target.value })}
                            />
                            <TimeChip t={t.t_ref} conf={t.confidence} onSeek={seekTo} />
                            <EvidenceThumb clipId={detail.id} trait={t} onSeek={seekTo} />
                          </li>
                        );
                      })}
                    </ul>
                  )}
                  <div className="va-row-gap va-mt">
                    <button className="btn primary" disabled={reviewing} onClick={submitReview}>
                      {reviewing ? "Đang lưu…" : "✓ Duyệt & lưu vào hồ sơ"}
                    </button>
                    {reEditing && (
                      <button className="btn" disabled={reviewing} onClick={() => setReEditing(false)}>
                        Hủy
                      </button>
                    )}
                  </div>
                </div>
              ) : (
                <div className="va-reviewed">
                  <div className="va-card-head">
                    <h4>✓ Đã duyệt — {acceptedTraits.length} nhận xét vào hồ sơ</h4>
                    <button className="btn" onClick={() => setReEditing(true)}>Sửa lại</button>
                  </div>
                  <div className="va-sw-cols">
                    <div>
                      <h4 className="va-strength-h">✅ Điểm mạnh</h4>
                      <ul className="va-sw-list">
                        {acceptedTraits.filter((t) => t.polarity === "strength").map((t) => (
                          <li key={t.id}>
                            <span className="va-aspect-tag">{ASPECT_LABEL[t.aspect] ?? t.aspect}</span>
                            {t.text}
                            <TimeChip t={t.t_ref} conf={t.confidence} onSeek={seekTo} />
                            <EvidenceThumb clipId={detail.id} trait={t} onSeek={seekTo} />
                          </li>
                        ))}
                        {acceptedTraits.filter((t) => t.polarity === "strength").length === 0 && (
                          <li className="va-muted">—</li>
                        )}
                      </ul>
                    </div>
                    <div>
                      <h4 className="va-weakness-h">⚠️ Điểm yếu</h4>
                      <ul className="va-sw-list">
                        {acceptedTraits.filter((t) => t.polarity === "weakness").map((t) => (
                          <li key={t.id}>
                            <span className="va-aspect-tag">{ASPECT_LABEL[t.aspect] ?? t.aspect}</span>
                            {t.text}
                            <TimeChip t={t.t_ref} conf={t.confidence} onSeek={seekTo} />
                            <EvidenceThumb clipId={detail.id} trait={t} onSeek={seekTo} />
                          </li>
                        ))}
                        {acceptedTraits.filter((t) => t.polarity === "weakness").length === 0 && (
                          <li className="va-muted">—</li>
                        )}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              <div className="va-aspect-blocks">
                {raw.serve && (raw.serve.type || raw.serve.notes) && (
                  <div className="va-aspect-block">
                    <h4>🏓 Giao bóng{raw.serve.type ? `: ${raw.serve.type}` : ""}</h4>
                    <p>{raw.serve.notes}</p>
                  </div>
                )}
                {raw.footwork?.notes && (
                  <div className="va-aspect-block">
                    <h4>👣 Bộ chân</h4>
                    <p>{raw.footwork.notes}</p>
                  </div>
                )}
                {raw.posture?.notes && (
                  <div className="va-aspect-block">
                    <h4>🧍 Tư thế / thân người</h4>
                    <p>{raw.posture.notes}</p>
                  </div>
                )}
              </div>

              {(raw.recommendations ?? []).length > 0 && (
                <div className="va-aspect-block">
                  <h4>🎯 Gợi ý luyện tập</h4>
                  <ul className="va-rec-list">
                    {raw.recommendations!.map((r, i) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}

              {a.progress && a.progress.length > 0 && (
                <div className="va-aspect-block">
                  <h4>📈 Tiến bộ so với các clip trước</h4>
                  <table className="va-pose-table">
                    <tbody>
                      {a.progress.map((t) => (
                        <tr key={t.name}>
                          <td>{t.label}</td>
                          <td>
                            {t.current}{t.unit}{" "}
                            <span className="va-muted">
                              (trước: {t.baseline}{t.unit} · {t.samples} clip)
                            </span>
                          </td>
                          <td><TrendChip t={t} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="va-muted">
                    So với trung bình các clip trước của chính bạn. “tốt hơn/kém hơn” theo
                    chiều có lợi của từng chỉ số (vd gối gập nhiều hơn = tốt).
                  </p>
                </div>
              )}

              <div className="va-aspect-block">
                <h4>📐 Số liệu pose (đo tự động)</h4>
                {poseAvailable ? (
                  <table className="va-pose-table">
                    <tbody>
                      <tr><td>Độ rộng tấn (so với vai)</td><td>{metricText(pose.stance_width_ratio)}</td></tr>
                      <tr><td>Góc gập gối</td><td>{metricText(pose.knee_flexion_deg, "°")}</td></tr>
                      <tr><td>Độ nghiêng thân</td><td>{metricText(pose.torso_lean_deg, "°")}</td></tr>
                      <tr><td>Biên độ di chuyển ngang (bộ chân)</td><td>{pose.lateral_sway ?? "—"}</td></tr>
                      <tr><td>Độ cao tay (so với vai)</td><td>{metricText(pose.hand_elevation)}</td></tr>
                      <tr><td>Khung phát hiện người</td><td>{pose.frames_with_pose}/{pose.frames_analyzed}</td></tr>
                    </tbody>
                  </table>
                ) : (
                  <p className="va-muted">{pose.reason || "Không có dữ liệu pose."}</p>
                )}
              </div>

              {a.ball?.available && (a.ball.zones?.length ?? 0) > 0 && (
                <div className="va-aspect-block">
                  <h4>🏓 Bóng & điểm rơi (thử nghiệm)</h4>
                  <div className="va-placement-wrap">
                    <PlacementGrid ball={a.ball} />
                    <div className="va-muted va-placement-legend">
                      <div>Lưới 3×3 mặt bàn: hàng trên = gần lưới, dưới = cuối bàn.</div>
                      <div>{a.ball.note}</div>
                      <div>
                        {a.ball.n_points} điểm · độ tin cậy TB{" "}
                        {Math.round((a.ball.mean_conf ?? 0) * 100)}% · cách{" "}
                        {a.ball.method === "tracknet" ? "TrackNet" : "chuyển động"}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
