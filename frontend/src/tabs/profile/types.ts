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
