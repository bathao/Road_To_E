import type { PlayerLevel } from "../../shared/levels";

// One row of the Database tab (player + appearance counts by role).
export interface PlayerDbRow {
  id: number;
  name: string;
  level: PlayerLevel; // legacy relative label (being retired)
  note?: string | null;
  plays_pips: boolean;
  points: number | null; // BBTV points, maintained by hand; null = not rated
  matches_vs: number; // as my opponent (either slot)
  matches_with: number; // as my partner
}

export interface PlayersDbResponse {
  players: PlayerDbRow[];
}

// MyRating lives in tabs/match-stats/types.ts — the user's dynamic rating
// header sits on the Profile page (the merged Match Stats tab).
