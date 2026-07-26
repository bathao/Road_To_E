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

// The user's rating: `points` is the editable ANCHOR; `current` is the
// replayed dynamic ELO (anchor + eligible matches since anchor_date — every
// involved player named + rated; doubles count at FULL weight on team
// averages; a chấp adds the receiver's full ladder bonus — a big chấp can
// make the receiver the favourite). PUT = new anchor from today.
export interface MyRating {
  points: number;
  current: number;
  anchor_date: string;
  counted_matches: number;
}

export interface RatingPoint {
  date: string; // ISO
  rating: number;
}

// Daily ELO curve since the anchor (replayed server-side, nothing stored).
export interface MyRatingHistory {
  anchor_date: string;
  anchor_points: number;
  current: number;
  points: RatingPoint[];
}
