import type { PlayerLevel } from "../../shared/levels";

// One row of the Database tab (player + appearance count).
export interface PlayerDbRow {
  id: number;
  name: string;
  level: PlayerLevel; // legacy relative label (being retired)
  note?: string | null;
  plays_pips: boolean;
  points: number | null; // BBTV points, maintained by hand; null = not rated
  matches_played: number;
}

export interface PlayersDbResponse {
  players: PlayerDbRow[];
}

export interface MyRating {
  points: number;
}
