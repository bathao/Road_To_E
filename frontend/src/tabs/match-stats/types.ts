// Types for the Match Stats tab. Mirror the backend MatchStatsResponse.
import type { PlayerLevel } from "../../shared/levels";
import type { MatchStats } from "../../shared/types";

export type { PlayerLevel, MatchStats };

export interface LevelRecord {
  level: PlayerLevel;
  stats: MatchStats;
}

export interface MatchLine {
  date: string;
  discipline: "singles" | "doubles";
  my_sets: number;
  opp_sets: number;
  result: "W" | "L" | "T";
  handicap: number;
  event_name: string | null;
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

export interface DoublesRecord {
  key: string;
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
}

export type DisciplineFilter = "all" | "singles" | "doubles";
export type CategoryFilter = "all" | "practice" | "official";

export interface MatchStatsResponse {
  date_from: string;
  date_to: string;
  discipline: DisciplineFilter;
  category: CategoryFilter;
  unit: "month" | "week" | "day";
  overall: MatchStats;
  by_level: LevelRecord[];
  opponents: OpponentBrief[];
  singles_h2h: OpponentRecord[];
  doubles_h2h: DoublesRecord[];
  trend: MatchTrendBucket[];
}
