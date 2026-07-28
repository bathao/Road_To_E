// Types for the Profile dashboard. Most data is reused from other tabs; these
// cover the tracker aggregates this tab reads.
import type { MatchStats } from "../../shared/types";
import type { PlayerLevel } from "../../shared/levels";

export type { MatchStats, PlayerLevel };

export interface CategoryMinutes {
  key: string;
  label: string;
  minutes: number;
}

/** Response of GET /api/tracker/stats — training volume over a date range. */
export interface TrackerStats {
  date_from: string;
  date_to: string;
  num_days: number;
  days_trained: number;
  days_physical: number;
  minutes_total: number;
  minutes_by_category: CategoryMinutes[];
  overall: MatchStats;
  singles: MatchStats;
  doubles: MatchStats;
}

export interface LevelRecord {
  level: PlayerLevel;
  stats: MatchStats;
}

/** Subset of GET /api/tracker/match-stats we use here. */
export interface MatchStatsLite {
  overall: MatchStats;
  by_level: LevelRecord[];
}

export type RangeKey = "30" | "90" | "365" | "all";

// ---- my dynamic ELO (moved here from the Database tab, 2026-07-27) ----

// `points` is the editable ANCHOR; `current` is the replayed dynamic ELO.
// PUT = new anchor from today.
export interface MyRating {
  points: number;
  current: number;
  anchor_date: string;
  counted_matches: number;
}

export interface RatingBucket {
  key: string;
  label: string;
  date_from: string;
  date_to: string;
  delta: number; // net ±Δ of the bucket's counted matches (0 when none)
  counted: number;
  rating_end: number | null; // carry-forward; null = bucket predates the anchor
}

// Subset of GET /tracker/my-rating/breakdown used for the since-anchor curve
// (same engine as the Daily Tracker's ELO chart — /my-rating/history retired
// 2026-07-28 in its favour).
export interface RatingBreakdown {
  anchor_date: string;
  anchor_points: number;
  total_delta: number;
  counted: number;
  rating_start: number | null;
  rating_end: number | null;
  buckets: RatingBucket[];
}
