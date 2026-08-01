// Types for the Profile tab (formerly Match Stats). Mirror the backend
// MatchStatsResponse.
import type { PlayerLevel } from "../../shared/levels";
import type { MatchStats } from "../../shared/types";

export type { PlayerLevel };

export interface MatchLine {
  date: string;
  discipline: "singles" | "doubles" | "one_v_two" | "two_v_one";
  my_sets: number;
  opp_sets: number;
  result: "W" | "L" | "T";
  handicap: number;
  handicap_pattern?: string | null; // per-set sequence ("2-0-2"); null = uniform
  event_name: string | null;
  round?: string | null; // tournament round ("group"/"qf"/…); null = n/a
}

export interface OpponentRecord {
  opponent_id: number;
  name: string;
  level: PlayerLevel;
  played: number;
  wins: number;
  losses: number;
  ties: number;
  sets_won: number;
  sets_lost: number;
  win_rate: number | null;
  last_date: string | null;
  last_result: "W" | "L" | "T" | null;
  matches: MatchLine[];
}

export interface OpponentBrief {
  id: number;
  name: string;
  level: PlayerLevel;
  played: number;
}

// A team-style matchup: doubles, 1v2 (me alone vs a pair) or 2v1
// (me + partner vs one player). Slots the format doesn't use stay null.
export interface DoublesRecord {
  key: string;
  discipline: "doubles" | "one_v_two" | "two_v_one";
  partner_id: number | null;
  partner_name: string | null;
  partner_level: PlayerLevel | null;
  opp1_id: number;
  opp1_name: string;
  opp1_level: PlayerLevel;
  opp2_id: number | null;
  opp2_name: string | null;
  opp2_level: PlayerLevel | null;
  played: number;
  wins: number;
  losses: number;
  ties: number;
  sets_won: number;
  sets_lost: number;
  win_rate: number | null;
  last_date: string | null;
  last_result: "W" | "L" | "T" | null;
  matches: MatchLine[];
}

export interface MatchTrendBucket {
  key: string;
  label: string;
  date_from: string;
  date_to: string;
  matches: number;
  wins: number;
  losses: number;
  win_rate: number | null;
  // Rolling form at the bucket's end: win rate of the last 10 decided
  // matches (null until enough matches have been played).
  form: number | null;
}

// My ELO over time (shared shapes with the Daily Tracker's Analysis panel).
export type { RatingBreakdown, RatingMover } from "../daily-tracker/types";

// ---- the Profile pieces merged into this tab (2026-07-30) ----

// Full response of GET /api/tracker/stats (same endpoint as the Daily
// Tracker) — feeds the Training discipline card.
export type { StatsResponse as TrackerStats } from "../daily-tracker/types";

// `points` is the editable ANCHOR; `current` is the replayed dynamic ELO.
// PUT = new anchor from today.
export interface MyRating {
  points: number;
  current: number;
  anchor_date: string;
  counted_matches: number;
}

export type DisciplineFilter =
  | "all"
  | "singles"
  | "doubles"
  | "one_v_two"
  | "two_v_one";
export type CategoryFilter = "all" | "practice" | "official" | "tournament";

export interface MatchStatsResponse {
  date_from: string;
  date_to: string;
  discipline: DisciplineFilter;
  category: CategoryFilter;
  unit: "month" | "week" | "day";
  overall: MatchStats;
  opponents: OpponentBrief[];
  singles_h2h: OpponentRecord[];
  doubles_h2h: DoublesRecord[];
  trend: MatchTrendBucket[];
}

// ------------------------- Tournament Record (read-only history, rangeless)
// Mirrors backend app/features/tournament/schemas.py (Record* models) —
// everything DERIVED from the Daily Tracker matches, nothing stored.

export interface RecordMatch {
  id: number;
  date: string;
  round: string | null; // group|r64|…|f; null = saved without a round
  discipline: string;
  opponent_name: string | null;
  opponent2_name: string | null;
  partner_name: string | null;
  my_sets: number;
  opp_sets: number;
  won: boolean | null; // null = no result entered
  elo_delta: number | null; // null = not ELO-counted (e.g. pre-anchor)
}

export interface RecordEntryInfo {
  id: number;
  discipline: string;
  partner_name: string | null;
  teammate_names: string[];
  team_members: string | null;
  division: string | null;
  final_placement: string | null;
  bonus_points: number | null;
  data_warning: string | null;
}

export interface RecordEntry {
  entry: RecordEntryInfo;
  round_reached: string | null; // deepest decided round; null = no matches
  reached_won: boolean;
  wins: number;
  losses: number;
  sets_won: number;
  sets_lost: number;
  matches: RecordMatch[];
}

export interface RecordTournament {
  id: number;
  name: string;
  location: string | null;
  start_date: string;
  end_date: string | null;
  level_limit: string | null;
  entries: RecordEntry[];
}

export interface TournamentRecordResponse {
  tournaments: RecordTournament[];
}
