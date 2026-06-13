import { useCallback, useEffect, useState } from "react";
import { videoApi } from "../video-analysis/api";
import { ASPECT_LABEL, SKILL_STATUS_LABEL } from "../video-analysis/labels";
import type { Profile, ProfileImage, Report, Skill, SkillStatus } from "../video-analysis/types";
import { LEVELS } from "../../shared/levels";
import { pct } from "../../shared/format";
import { trainingApi } from "../training-center/api";
import type { Report as TrainingReport } from "../training-center/types";
import { profileApi } from "./api";
import type { MatchStatsLite, RangeKey, TrackerStats } from "./types";
import SkillRadar from "./components/SkillRadar";

const STATUS_CLASS: Record<SkillStatus, string> = {
  strength: "va-sk-strong",
  improving: "va-sk-improving",
  neutral: "va-sk-neutral",
  needs_work: "va-sk-needswork",
  weakness: "va-sk-weak",
};

const RANGES: { key: RangeKey; label: string }[] = [
  { key: "30", label: "30 ngày" },
  { key: "90", label: "90 ngày" },
  { key: "365", label: "1 năm" },
  { key: "all", label: "Tất cả" },
];

function isoRange(range: RangeKey): { from: string; to: string } {
  const now = new Date();
  const to = now.toISOString().slice(0, 10);
  if (range === "all") return { from: "2026-01-01", to };
  const f = new Date(now);
  f.setDate(f.getDate() - parseInt(range, 10));
  return { from: f.toISOString().slice(0, 10), to };
}

function hoursLabel(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m} phút`;
  return m === 0 ? `${h} giờ` : `${h} giờ ${m} phút`;
}

export default function PlayerProfile() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [images, setImages] = useState<ProfileImage[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [trainingReport, setTrainingReport] = useState<TrainingReport | null>(null);
  const [lastDate, setLastDate] = useState<string | null>(null);

  const [range, setRange] = useState<RangeKey>("90");
  const [training, setTraining] = useState<TrackerStats | null>(null);
  const [match, setMatch] = useState<MatchStatsLite | null>(null);

  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));

  const reloadSkillData = useCallback(async () => {
    const [sk, rp] = await Promise.all([videoApi.listSkills(), videoApi.getReport()]);
    setSkills(sk);
    setReport(rp);
  }, []);

  // Identity + skill data (not date-ranged).
  useEffect(() => {
    (async () => {
      try {
        const [p, im, sk, rp, ld, tr] = await Promise.all([
          videoApi.getProfile(),
          videoApi.listProfileImages(),
          videoApi.listSkills(),
          videoApi.getReport(),
          profileApi.lastDate(),
          trainingApi.getReport(),
        ]);
        setProfile(p);
        setImages(im);
        setSkills(sk);
        setReport(rp);
        setLastDate(ld.date);
        setTrainingReport(tr);
      } catch (e) {
        fail(e);
      }
    })();
  }, []);

  // Training + match aggregates follow the range selector.
  useEffect(() => {
    const { from, to } = isoRange(range);
    (async () => {
      try {
        const [tr, ms] = await Promise.all([
          profileApi.trainingStats(from, to),
          profileApi.matchStats(from, to),
        ]);
        setTraining(tr);
        setMatch(ms);
      } catch (e) {
        fail(e);
      }
    })();
  }, [range]);

  const handleRegenerate = async () => {
    setError(null);
    setRegenerating(true);
    try {
      await videoApi.regenerateSkills();
      await reloadSkillData();
    } catch (e) {
      fail(e);
    } finally {
      setRegenerating(false);
    }
  };

  if (!profile) {
    return (
      <div className="va-tab">
        {error && <div className="pb-error">{error}</div>}
        <p className="va-muted">Đang tải hồ sơ…</p>
      </div>
    );
  }

  const hasRatings = skills.some((s) => s.rating != null);
  const canRegenerate = (report?.findings_accepted ?? 0) > 0;
  // Prefer a manually-added portrait (source_clip_id == null) as the avatar so
  // auto-generated crops from clips never override it; fall back to newest.
  const avatarImg = images.find((i) => i.source_clip_id == null) ?? images[0];
  const avatar = avatarImg ? videoApi.profileImageUrl(avatarImg.id) : null;
  const byLevel = new Map((match?.by_level ?? []).map((r) => [r.level, r.stats]));

  return (
    <div className="va-tab prof-tab">
      {error && <div className="pb-error">{error}</div>}

      {/* 1) Header */}
      <section className="va-card prof-header">
        {avatar ? (
          <img className="prof-avatar" src={avatar} alt={profile.name} />
        ) : (
          <div className="prof-avatar prof-avatar-blank">🏓</div>
        )}
        <div className="prof-header-main">
          <h2 className="prof-name">{profile.name}</h2>
          <div className="va-basics">
            <span className="va-chip">Thuận tay: {profile.handed === "left" ? "Trái" : "Phải"}</span>
            <span className="va-chip">Vợt: {profile.grip === "penhold" ? "Dọc" : "Ngang"}</span>
            {profile.style && <span className="va-chip">Lối đánh: {profile.style}</span>}
            {profile.equipment && <span className="va-chip">Dụng cụ: {profile.equipment}</span>}
            {profile.physique && <span className="va-chip">Thể hình: {profile.physique}</span>}
          </div>
          {profile.overall_summary ? (
            <p className="prof-overall">{profile.overall_summary}</p>
          ) : (
            <p className="va-muted">
              Chưa có tổng quan. Duyệt nhận xét trong tab Video Analysis rồi "Cập nhật hồ sơ".
            </p>
          )}
          {lastDate && <p className="va-muted prof-asof">Dữ liệu tính đến {lastDate}</p>}
        </div>
      </section>

      {/* 2) Skills: radar + bars */}
      <section className="va-card">
        <div className="va-card-head">
          <h3>📊 Kỹ năng</h3>
          <button className="btn" disabled={regenerating || !canRegenerate}
            title={canRegenerate ? "" : "Cần có nhận xét đã duyệt trước khi dựng hồ sơ"}
            onClick={handleRegenerate}>
            {regenerating ? "Đang dựng…" : "↻ Cập nhật hồ sơ kỹ năng"}
          </button>
        </div>
        {!hasRatings && (
          <p className="va-muted">
            Chưa có điểm kỹ năng. Vào tab Video Analysis → phân tích & duyệt clip → bấm
            "Cập nhật hồ sơ kỹ năng".
          </p>
        )}
        <div className="prof-skill-grid">
          <SkillRadar skills={skills} />
          <div className="prof-skill-bars">
            {skills.map((s) => (
              <div key={s.aspect} className="prof-bar-row">
                <span className="prof-bar-name">{ASPECT_LABEL[s.aspect] ?? s.aspect}</span>
                <div className="va-skill-bar">
                  <div className={`va-skill-bar-fill ${STATUS_CLASS[s.status]}`}
                    style={{ width: `${((s.rating ?? 0) / 10) * 100}%` }} />
                </div>
                <span className="prof-bar-val">{s.rating == null ? "—" : `${s.rating}/10`}</span>
                <span className={`va-chip va-sk-chip ${STATUS_CLASS[s.status]}`}>
                  {SKILL_STATUS_LABEL[s.status]}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 3) Strengths / weaknesses */}
      {report && (report.strengths.length > 0 || report.weaknesses.length > 0) && (
        <section className="va-card">
          <div className="va-sw-cols">
            <div>
              <h4 className="va-strength-h">✅ Điểm mạnh</h4>
              <ul className="va-sw-list">
                {report.strengths.map((t, i) => <li key={i}>{t}</li>)}
                {report.strengths.length === 0 && <li className="va-muted">—</li>}
              </ul>
            </div>
            <div>
              <h4 className="va-weakness-h">⚠️ Điểm yếu</h4>
              <ul className="va-sw-list">
                {report.weaknesses.map((t, i) => <li key={i}>{t}</li>)}
                {report.weaknesses.length === 0 && <li className="va-muted">—</li>}
              </ul>
            </div>
          </div>
        </section>
      )}

      {/* 4) Improvement priorities */}
      {report && report.improvement_priorities.length > 0 && (
        <section className="va-card">
          <h3>🎯 Ưu tiên cải thiện</h3>
          <ol className="va-priority-list">
            {report.improvement_priorities.map((p, i) => <li key={i}>{p}</li>)}
          </ol>
        </section>
      )}

      {/* range selector for the competitive + training snapshots */}
      <div className="prof-range">
        <span className="va-muted">Khoảng thời gian:</span>
        {RANGES.map((r) => (
          <button key={r.key}
            className={`btn${range === r.key ? " primary" : ""}`}
            onClick={() => setRange(r.key)}>
            {r.label}
          </button>
        ))}
      </div>

      {/* 5) Competitive snapshot */}
      <section className="va-card">
        <h3>🏆 Thành tích thi đấu</h3>
        {match && match.overall.total > 0 ? (
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-card-title">Tỉ lệ thắng (tổng)</div>
              <div className="stat-big">{pct(match.overall.win_rate)}</div>
              <div className="stat-line muted">
                <span>{match.overall.total} trận</span>
                <span><span className="win">{match.overall.wins}T</span> · <span className="loss">{match.overall.losses}B</span></span>
              </div>
            </div>
            {LEVELS.map((lv) => {
              const st = byLevel.get(lv.key);
              return (
                <div key={lv.key} className="stat-card">
                  <div className="stat-card-title">Đối thủ {lv.label}</div>
                  <div className="stat-big">{pct(st?.win_rate ?? null)}</div>
                  <div className="stat-line muted">
                    <span>{st?.total ?? 0} trận</span>
                    <span>
                      <span className="win">{st?.wins ?? 0}T</span> · <span className="loss">{st?.losses ?? 0}B</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="va-muted">Chưa có trận có tên đối thủ trong khoảng này.</p>
        )}
      </section>

      {/* 6) Training discipline */}
      <section className="va-card">
        <h3>🏋️ Kỷ luật tập luyện</h3>
        {training ? (
          <>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-card-title">Ngày có tập</div>
                <div className="stat-big">{training.days_trained}</div>
                <div className="stat-line muted"><span>trên {training.num_days} ngày</span></div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Tổng thời lượng</div>
                <div className="stat-big">{(training.minutes_total / 60).toFixed(1)}h</div>
                <div className="stat-line muted"><span>{hoursLabel(training.minutes_total)}</span></div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Buổi thể lực</div>
                <div className="stat-big">{training.days_physical}</div>
                <div className="stat-line muted"><span>ngày có tập thể lực</span></div>
              </div>
            </div>
            {training.minutes_by_category.length > 0 && (
              <div className="prof-cat-list">
                {training.minutes_by_category.map((c) => (
                  <div key={c.key} className="stat-line">
                    <span>{c.label}</span>
                    <span>{hoursLabel(c.minutes)}</span>
                  </div>
                ))}
              </div>
            )}
          </>
        ) : (
          <p className="va-muted">Đang tải…</p>
        )}
      </section>

      {/* 7) Training Center (off-table physical program) */}
      <section className="va-card">
        <h3>💪 Training Center</h3>
        {trainingReport && trainingReport.total_sessions_done > 0 ? (
          <>
            <p className="va-muted">{trainingReport.summary_vi}</p>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-card-title">Cấp độ</div>
                <div className="stat-big" style={{ fontSize: "1.3rem" }}>
                  {trainingReport.current_level_vi}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Buổi đã hoàn thành</div>
                <div className="stat-big">{trainingReport.total_sessions_done}</div>
                <div className="stat-line muted">
                  <span>{trainingReport.sessions_last_7d} buổi / 7 ngày</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Buổi gần nhất</div>
                <div className="stat-big">
                  {trainingReport.days_since_last ?? "—"}
                </div>
                <div className="stat-line muted"><span>ngày trước</span></div>
              </div>
            </div>
            <div className="prof-cat-list">
              {(["legs", "core", "balance"] as const).map((k) => (
                <div key={k} className="stat-line">
                  <span>
                    {k === "legs" ? "🦵 Chân" : k === "core" ? "🌀 Lõi" : "⚖️ Cân bằng"}
                  </span>
                  <span>{trainingReport.day_type_counts[k] ?? 0} buổi</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="va-muted">
            Chưa có buổi tập nào. Vào tab Training Center 💪 để bắt đầu.
          </p>
        )}
      </section>
    </div>
  );
}
