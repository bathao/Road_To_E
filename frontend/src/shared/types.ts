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

/** Minutes spent in one tracker category over a range. */
export interface CategoryMinutes {
  key: string;
  label: string;
  minutes: number;
}

/** Result of a single match. */
export type MatchResult = "W" | "L" | "T";

/** W/L filter choice on the match drill-down modals. */
export type ResultFilter = "all" | "W" | "L";

/** W/L/T of a match derived from its set counts. */
export function resultOf(m: { my_sets: number; opp_sets: number }): MatchResult {
  return m.my_sets > m.opp_sets ? "W" : m.my_sets < m.opp_sets ? "L" : "T";
}
