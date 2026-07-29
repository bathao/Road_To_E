// Profile tab: my dynamic ELO + competitive record + training discipline.
// The skill/trait boards (manual knowledge base of the retired video-analysis
// pipeline) were deleted 2026-07-29; their va_* rows stay in the DB.
import { useState } from "react";
import { addDays, toIso } from "../../shared/dates";
import { useLoad } from "../../shared/useApi";
import { trainingApi } from "../training-center/api";
import { profileApi } from "./api";
import type { RangeKey } from "./types";
import MyRatingCard from "./components/MyRatingCard";
import CompetitiveCard from "./components/CompetitiveCard";
import TrainingDisciplineCard from "./components/TrainingDisciplineCard";
import TrainingCenterCard from "./components/TrainingCenterCard";

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

export default function PlayerProfile() {
  const [range, setRange] = useState<RangeKey>("90");

  // Not date-ranged: the "as of" date and the Training Center report.
  const { data: lastDate } = useLoad(() => profileApi.lastDate(), []);
  const { data: trainingReport, error: reportError } = useLoad(
    () => trainingApi.getReport(),
    []
  );

  // Training + match aggregates follow the range selector; useLoad's seq
  // counter drops out-of-order responses (fast range clicks) so the cards
  // never show a different range than the selected button.
  const { data: ranged, error: rangedError } = useLoad(async () => {
    const { from, to } = isoRange(range);
    const [training, match] = await Promise.all([
      profileApi.trainingStats(from, to),
      profileApi.matchStats(from, to),
    ]);
    return { training, match };
  }, [range]);

  const error = rangedError ?? reportError;

  return (
    <div className="va-tab prof-tab">
      {error && <div className="pb-error">{error}</div>}

      {/* 1) Header */}
      <section className="va-card prof-header">
        <div className="prof-avatar prof-avatar-blank">🏓</div>
        <div className="prof-header-main">
          <h2 className="prof-name">Player profile</h2>
          <p className="va-muted">ELO, competitive record and training progress.</p>
          {lastDate?.date && (
            <p className="va-muted prof-asof">Data as of {lastDate.date}</p>
          )}
        </div>
      </section>

      {/* 2) My dynamic ELO (big number + anchor edit + since-anchor curve) */}
      <MyRatingCard />

      {/* range selector for the competitive + training snapshots */}
      <div className="prof-range">
        <span className="va-muted">Time range:</span>
        {RANGES.map((r) => (
          <button
            key={r.key}
            className={`btn${range === r.key ? " primary" : ""}`}
            onClick={() => setRange(r.key)}
          >
            {r.label}
          </button>
        ))}
      </div>

      {/* 3) Competitive snapshot */}
      <CompetitiveCard match={ranged?.match ?? null} />

      {/* 4) Training discipline */}
      <TrainingDisciplineCard training={ranged?.training ?? null} />

      {/* 5) Training Center (off-table physical program) */}
      <TrainingCenterCard report={trainingReport} />
    </div>
  );
}
