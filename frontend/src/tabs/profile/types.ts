// Types for the Profile dashboard. Everything the tab reads comes from
// existing tracker/training endpoints; most shapes are shared with other tabs.
import type { LevelRecord, MatchStats } from "../../shared/types";
import type { PlayerLevel } from "../../shared/levels";

export type { LevelRecord, MatchStats, PlayerLevel };

// Full response of GET /api/tracker/stats (same endpoint as the Daily Tracker).
export type { StatsResponse as TrackerStats } from "../daily-tracker/types";

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

// Same curve engine + shapes as the Daily Tracker's ELO chart
// (/my-rating/history retired 2026-07-28 in favour of /my-rating/breakdown).
export type { RatingBreakdown, RatingBucket } from "../daily-tracker/types";
