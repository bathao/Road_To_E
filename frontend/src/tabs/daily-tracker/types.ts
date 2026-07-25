// Mirrors the backend Pydantic schemas (app/features/tracker/schemas.py).

export type CategoryType =
  | "duration"
  | "match"
  | "rating"
  | "checklist"
  | "note"
  | "computed"; // auto-calculated read-only row (Racket Time)
export type ColorGroup = "green" | "yellow" | "none";
export type Discipline = "singles" | "doubles";

export interface Category {
  id: number;
  key: string;
  label: string;
  type: CategoryType;
  color_group: ColorGroup;
  sort_order: number;
}

export interface Activity {
  id: number;
  date: string; // YYYY-MM-DD
  category_id: number;
  duration_minutes: number;
  note: string | null;
  is_package_start: boolean; // first session of a coaching package
}

// Skill level of a player relative to me (canonical definition in shared/).
import type { PlayerLevel } from "../../shared/levels";
export type { PlayerLevel };

export interface Player {
  id: number;
  name: string;
  level: PlayerLevel;
  note?: string | null;
  plays_pips: boolean; // opponent uses pimpled rubber ("đánh gai")
}

export interface PlayerIn {
  name: string;
  level: PlayerLevel;
  note?: string | null;
  plays_pips?: boolean;
}

export interface Match {
  id: number;
  date: string;
  category_id: number;
  discipline: Discipline;
  best_of: number; // 3 | 5 | 7
  my_sets: number;
  opp_sets: number;
  event_id: number | null;
  event_name: string | null;
  is_nonplaying: boolean;
  nonplaying_label: string | null; // "Travel" | "Rest"
  note: string | null;
  order_index: number;
  // Who played. Singles: opponent_*. Doubles: partner_* + opponent_* + opponent2_*.
  opponent_id: number | null;
  opponent_name: string | null;
  opponent_level: PlayerLevel | null;
  opponent_plays_pips: boolean;
  opponent2_id: number | null;
  opponent2_name: string | null;
  opponent2_level: PlayerLevel | null;
  opponent2_plays_pips: boolean;
  partner_id: number | null;
  partner_name: string | null;
  partner_level: PlayerLevel | null;
  handicap: number; // signed: +N = I give N points, -N = I receive
}

export interface CellData {
  display: string;
  color: string | null;
}

export interface WeekResponse {
  start: string;
  days: string[]; // 7 ISO dates, Mon..Sun
  categories: Category[];
  activities: Activity[];
  matches: Match[];
  cells: Record<string, CellData>; // key = `${category_id}|${isoDate}`
  physical_checks: Record<string, string[]>; // isoDate -> ticked item keys (legacy)
  day_notes: Record<string, string>; // isoDate -> note text
  // From this date forward the Physical row mirrors Training Center (read-only
  // in the grid). null = unset (no Training Center activity yet).
  physical_cutover: string | null;
}

export interface PhysicalItem {
  key: string;
  label: string;
}

// ---- stats / analysis ----
import type { MatchStats } from "../../shared/types";
export type { MatchStats };

export interface CategoryMinutes {
  key: string;
  label: string;
  minutes: number;
}

export interface BreakdownBucket {
  key: string;
  label: string;
  date_from: string;
  date_to: string;
  minutes: number;
  days_trained: number;
  days_physical: number;
  matches: number;
  wins: number;
  losses: number;
  win_rate: number | null;
}

export interface BreakdownResponse {
  unit: "month" | "week" | "day";
  buckets: BreakdownBucket[];
}

export interface StatsResponse {
  date_from: string;
  date_to: string;
  num_days: number;
  days_trained: number;
  days_physical: number;
  minutes_total: number;
  minutes_by_category: CategoryMinutes[];
  // Racket time = coach + partner training + match play (sets × ~5 min).
  racket_minutes_total: number;
  racket_minutes_training: number;
  racket_minutes_matches: number;
  overall: MatchStats;
  singles: MatchStats;
  doubles: MatchStats;
  vs_pips: MatchStats; // matches vs a pimpled-rubber opponent ("gai")
}

// ---- request payloads ----
export interface ActivityIn {
  date: string;
  category_id: number;
  duration_minutes: number;
  note?: string | null;
  is_package_start?: boolean;
}

// ---- tournaments (scheduling commitments; match results stay in the grid) ----
export type TournamentDiscipline = "singles" | "doubles" | "team";

export interface TournamentEntry {
  id: number;
  discipline: TournamentDiscipline;
  partner_id?: number | null;
  partner_name?: string | null; // resolved by the backend for display
  teammate_ids?: number[]; // team roster (players from the shared pool)
  teammate_names?: string[]; // resolved, same order as ids
  team_members?: string | null; // optional team name / note
  division?: string | null; // "hạng E", "U40"…
}

export interface Tournament {
  id: number;
  name: string;
  location?: string | null;
  start_date: string;
  end_date?: string | null; // null = single-day
  level_limit?: string | null; // allowed ranks, free text ("E F G"…)
  note?: string | null;
  entries: TournamentEntry[];
}

export interface TournamentEntryIn {
  discipline: TournamentDiscipline;
  partner_id?: number | null;
  teammate_ids?: number[];
  team_members?: string | null;
  division?: string | null;
}

export interface TournamentIn {
  name: string;
  location?: string | null;
  start_date: string;
  end_date?: string | null;
  level_limit?: string | null;
  note?: string | null;
  entries: TournamentEntryIn[];
}

export interface TournamentsResponse {
  // Upcoming first (soonest on top), then past (newest first).
  tournaments: Tournament[];
}

// ---- coach packages (10-session blocks) ----
export type CoachPackageStatus = "ok" | "low" | "done" | "over";

export interface CoachPackage {
  number: number;
  start_date: string;
  end_date: string;
  used: number;
  size: number;
  remaining: number;
  over: number;
  is_current: boolean;
  status: CoachPackageStatus;
}

export interface CoachPackagesResponse {
  size: number;
  packages: CoachPackage[];
}

export interface MatchIn {
  date: string;
  category_id: number;
  discipline?: Discipline;
  best_of?: number;
  my_sets?: number;
  opp_sets?: number;
  event_name?: string | null;
  is_nonplaying?: boolean;
  nonplaying_label?: string | null;
  note?: string | null;
  order_index?: number;
  opponent_id?: number | null;
  opponent2_id?: number | null;
  partner_id?: number | null;
  handicap?: number;
}

export interface EventOut {
  id: number;
  name: string;
}

export const cellKey = (categoryId: number, isoDate: string) =>
  `${categoryId}|${isoDate}`;
