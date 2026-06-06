// Domain types shared by more than one tab.

/** Aggregate W/L/T record over a set of matches. */
export interface MatchStats {
  total: number;
  wins: number;
  losses: number;
  ties: number;
  sets_won: number;
  sets_lost: number;
  win_rate: number | null; // 0..1
}

/** Result of a single match. */
export type MatchResult = "W" | "L" | "T";
