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

// MyRating / MyRatingHistory moved to tabs/profile/types.ts (2026-07-27) —
// the user's dynamic rating card lives on the Profile tab now.
