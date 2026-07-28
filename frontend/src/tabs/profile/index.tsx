import { useCallback, useEffect, useState } from "react";
import { videoApi } from "./engine/api";
import {
  ASPECT_LABEL,
  SKILL_STATUS_CLASS,
  SKILL_STATUS_LABEL,
} from "./engine/labels";
import type {
  Aspect,
  Profile,
  ProfileIn,
  Report,
  Setting,
  Skill,
  SkillIn,
  Trait,
  TraitIn,
} from "./engine/types";
import ProfilePanel from "./engine/components/ProfilePanel";
import SkillBoard from "./engine/components/SkillBoard";
import TraitBoard from "./engine/components/TraitBoard";
import { LEVELS } from "../../shared/levels";
import { pct } from "../../shared/format";
import { addDays, toIso } from "../../shared/dates";
import { trainingApi } from "../training-center/api";
import type { Report as TrainingReport } from "../training-center/types";
import { profileApi } from "./api";
import type { MatchStatsLite, RangeKey, TrackerStats } from "./types";
import SkillRadar from "./components/SkillRadar";
import MyRatingCard from "./components/MyRatingCard";

const RANGES: { key: RangeKey; label: string }[] = [
  { key: "30", label: "30 days" },
  { key: "90", label: "90 days" },
  { key: "365", label: "1 year" },
  { key: "all", label: "All" },
];

function isoRange(range: RangeKey): { from: string; to: string } {
  // LOCAL calendar day (shared/dates), never toISOString(): UTC would put
  // "today" on yesterday before 7am in Vietnam and hide the day's data.
  const now = new Date();
  const to = toIso(now);
  // "All": a floor safely before any recorded data (data itself bounds the stats).
  if (range === "all") return { from: "2000-01-01", to };
  return { from: toIso(addDays(now, -parseInt(range, 10))), to };
}

function hoursLabel(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}

export default function PlayerProfile() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [skillSetting, setSkillSetting] = useState<Setting>("match");
  const [traits, setTraits] = useState<Trait[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [trainingReport, setTrainingReport] = useState<TrainingReport | null>(null);
  const [lastDate, setLastDate] = useState<string | null>(null);

  const [range, setRange] = useState<RangeKey>("90");
  const [training, setTraining] = useState<TrackerStats | null>(null);
  const [match, setMatch] = useState<MatchStatsLite | null>(null);

  const [regenSkills, setRegenSkills] = useState(false);
  const [regenSummary, setRegenSummary] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fail = (e: unknown) => setError(e instanceof Error ? e.message : String(e));

  const reloadSkillData = useCallback(async () => {
    const [sk, rp] = await Promise.all([videoApi.listSkills(), videoApi.getReport()]);
    setSkills(sk);
    setReport(rp);
  }, []);
  const reloadTraits = useCallback(
    async () => setTraits(await videoApi.listTraits("accepted")),
    []
  );

  // Identity + skill data (not date-ranged).
  useEffect(() => {
    (async () => {
      try {
        const [p, sk, t, rp, ld, tr] = await Promise.all([
          videoApi.getProfile(),
          videoApi.listSkills(),
          videoApi.listTraits("accepted"),
          videoApi.getReport(),
          profileApi.lastDate(),
          trainingApi.getReport(),
        ]);
        setProfile(p);
        setSkills(sk);
        setTraits(t);
        setReport(rp);
        setLastDate(ld.date);
        setTrainingReport(tr);
        setError(null); // a success clears any earlier banner
      } catch (e) {
        fail(e);
      }
    })();
  }, []);

  // Training + match aggregates follow the range selector. `alive` drops
  // out-of-order responses (fast range clicks) so the cards never show a
  // different range than the selected button.
  useEffect(() => {
    const { from, to } = isoRange(range);
    let alive = true;
    (async () => {
      try {
        const [tr, ms] = await Promise.all([
          profileApi.trainingStats(from, to),
          profileApi.matchStats(from, to),
        ]);
        if (!alive) return;
        setTraining(tr);
        setMatch(ms);
        setError(null);
      } catch (e) {
        if (alive) fail(e);
      }
    })();
    return () => {
      alive = false;
    };
  }, [range]);

  // ---- profile (basics + AI summary) ----
  const handleSaveProfile = async (payload: ProfileIn) => {
    try {
      setProfile(await videoApi.updateProfile(payload));
    } catch (e) {
      fail(e);
    }
  };
  const handleRegenerateSummary = async () => {
    setError(null);
    setRegenSummary(true);
    try {
      setProfile(await videoApi.regenerateSummary());
    } catch (e) {
      fail(e);
    } finally {
      setRegenSummary(false);
    }
  };

  // ---- skills ----
  const handleRegenerateSkills = async () => {
    setError(null);
    setRegenSkills(true);
    try {
      await videoApi.regenerateSkills();
      await reloadSkillData();
    } catch (e) {
      fail(e);
    } finally {
      setRegenSkills(false);
    }
  };
  const handleUpdateSkill = async (aspect: Aspect, setting: Setting, payload: SkillIn) => {
    try {
      await videoApi.updateSkill(setting, aspect, payload);
      await reloadSkillData();
    } catch (e) {
      fail(e);
    }
  };

  // ---- findings (manual knowledge base) ----
  const handleAddTrait = async (payload: TraitIn) => {
    try {
      await videoApi.createTrait(payload);
      await Promise.all([reloadTraits(), reloadSkillData()]);
    } catch (e) {
      fail(e);
    }
  };
  const handleDeleteTrait = async (id: number) => {
    try {
      await videoApi.deleteTrait(id);
      await Promise.all([reloadTraits(), reloadSkillData()]);
    } catch (e) {
      fail(e);
    }
  };

  if (!profile) {
    return (
      <div className="va-tab">
        {error && <div className="pb-error">{error}</div>}
        <p className="va-muted">Loading profile…</p>
      </div>
    );
  }

  const settingSkills = skills.filter((s) => s.setting === skillSetting);
  const hasRatings = settingSkills.some((s) => s.rating != null);
  const canRegenerateSkills = (report?.findings_accepted ?? 0) > 0;
  const byLevel = new Map((match?.by_level ?? []).map((r) => [r.level, r.stats]));

  return (
    <div className="va-tab prof-tab">
      {error && <div className="pb-error">{error}</div>}

      {/* 1) Header */}
      <section className="va-card prof-header">
        <div className="prof-avatar prof-avatar-blank">🏓</div>
        <div className="prof-header-main">
          <h2 className="prof-name">{profile.name}</h2>
          <p className="va-muted">Athlete profile — skills, strengths/weaknesses, progress.</p>
          {lastDate && <p className="va-muted prof-asof">Data as of {lastDate}</p>}
        </div>
      </section>

      {/* 2) My dynamic ELO (big number + anchor edit + since-anchor curve) */}
      <MyRatingCard />

      {/* 3) Identity + AI summary (editable) */}
      <ProfilePanel
        profile={profile}
        onSave={handleSaveProfile}
        onRegenerate={handleRegenerateSummary}
        regenerating={regenSummary}
        canRegenerate={traits.length > 0}
      />

      {/* 3) Skills radar (visual overview, per setting) */}
      <section className="va-card">
        <div className="va-card-head">
          <h3>📊 Skill overview</h3>
          <div className="seg prof-skill-seg">
            {(["practice", "match"] as Setting[]).map((st) => (
              <button
                key={st}
                className={`seg-btn${skillSetting === st ? " active" : ""}`}
                onClick={() => setSkillSetting(st)}
              >
                {st === "practice" ? "🏓 Practice" : "🔥 Match"}
              </button>
            ))}
          </div>
        </div>
        {hasRatings ? (
          <div className="prof-skill-grid">
            <SkillRadar skills={settingSkills} />
            <div className="prof-skill-bars">
              {settingSkills.map((s) => (
                <div key={s.aspect} className="prof-bar-row">
                  <span className="prof-bar-name">{ASPECT_LABEL[s.aspect] ?? s.aspect}</span>
                  <div className="va-skill-bar">
                    <div className={`va-skill-bar-fill ${SKILL_STATUS_CLASS[s.status]}`}
                      style={{ width: `${((s.rating ?? 0) / 10) * 100}%` }} />
                  </div>
                  <span className="prof-bar-val">{s.rating == null ? "—" : `${s.rating}/10`}</span>
                  <span className={`va-chip va-sk-chip ${SKILL_STATUS_CLASS[s.status]}`}>
                    {SKILL_STATUS_LABEL[s.status]}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <p className="va-muted">
            No {skillSetting === "match" ? "match" : "practice"} skill ratings yet. Paste an
            analysis in the Technique Analysis tab → ratings update automatically.
          </p>
        )}
      </section>

      {/* 4) Skill ledger (detail: edit, assessment, trend, practice-vs-match) */}
      <SkillBoard
        skills={skills}
        report={report}
        regenerating={regenSkills}
        canRegenerate={canRegenerateSkills}
        onRegenerate={handleRegenerateSkills}
        onUpdateSkill={handleUpdateSkill}
      />

      {/* 5) Confirmed findings (knowledge base, manual add) */}
      <TraitBoard traits={traits} onAdd={handleAddTrait} onDelete={handleDeleteTrait} />

      {/* range selector for the competitive + training snapshots */}
      <div className="prof-range">
        <span className="va-muted">Time range:</span>
        {RANGES.map((r) => (
          <button key={r.key}
            className={`btn${range === r.key ? " primary" : ""}`}
            onClick={() => setRange(r.key)}>
            {r.label}
          </button>
        ))}
      </div>

      {/* 6) Competitive snapshot */}
      <section className="va-card">
        <h3>🏆 Competitive record</h3>
        {match && match.overall.total > 0 ? (
          <div className="stat-grid">
            <div className="stat-card">
              <div className="stat-card-title">Win rate (overall)</div>
              <div className="stat-big">{pct(match.overall.win_rate)}</div>
              <div className="stat-line muted">
                <span>{match.overall.total} matches</span>
                <span><span className="win">{match.overall.wins}W</span> · <span className="loss">{match.overall.losses}L</span></span>
              </div>
            </div>
            {LEVELS.map((lv) => {
              const st = byLevel.get(lv.key);
              return (
                <div key={lv.key} className="stat-card">
                  <div className="stat-card-title">Opponents {lv.label}</div>
                  <div className="stat-big">{pct(st?.win_rate ?? null)}</div>
                  <div className="stat-line muted">
                    <span>{st?.total ?? 0} matches</span>
                    <span>
                      <span className="win">{st?.wins ?? 0}W</span> · <span className="loss">{st?.losses ?? 0}L</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="va-muted">No matches with a named opponent in this range.</p>
        )}
      </section>

      {/* 7) Training discipline */}
      <section className="va-card">
        <h3>🏋️ Training discipline</h3>
        {training ? (
          <>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-card-title">Days trained</div>
                <div className="stat-big">{training.days_trained}</div>
                <div className="stat-line muted"><span>of {training.num_days} days</span></div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Total time</div>
                <div className="stat-big">{(training.minutes_total / 60).toFixed(1)}h</div>
                <div className="stat-line muted"><span>{hoursLabel(training.minutes_total)}</span></div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Fitness sessions</div>
                <div className="stat-big">{training.days_physical}</div>
                <div className="stat-line muted"><span>days with fitness work</span></div>
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
          <p className="va-muted">Loading…</p>
        )}
      </section>

      {/* 8) Training Center (off-table physical program) */}
      <section className="va-card">
        <h3>💪 Training Center</h3>
        {trainingReport && trainingReport.total_sessions_done > 0 ? (
          <>
            <p className="va-muted">{trainingReport.summary_vi}</p>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-card-title">Level</div>
                <div className="stat-big" style={{ fontSize: "1.3rem" }}>
                  {trainingReport.current_level_vi}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Sessions completed</div>
                <div className="stat-big">{trainingReport.total_sessions_done}</div>
                <div className="stat-line muted">
                  <span>{trainingReport.sessions_last_7d} sessions / 7 days</span>
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-card-title">Last session</div>
                <div className="stat-big">
                  {trainingReport.days_since_last ?? "—"}
                </div>
                <div className="stat-line muted"><span>days ago</span></div>
              </div>
            </div>
            <div className="prof-cat-list">
              {(["legs", "core", "balance"] as const).map((k) => (
                <div key={k} className="stat-line">
                  <span>
                    {k === "legs" ? "🦵 Legs" : k === "core" ? "🌀 Core" : "⚖️ Balance"}
                  </span>
                  <span>{trainingReport.day_type_counts[k] ?? 0} sessions</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <p className="va-muted">
            No sessions yet. Open the Training Center tab 💪 to get started.
          </p>
        )}
      </section>
    </div>
  );
}
