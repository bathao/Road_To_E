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
// replayed dynamic ELO (anchor + eligible matches since anchor_date —
// singles, named rated opponent, no handicap). PUT = new anchor from today.
export interface MyRating {
  points: number;
  current: number;
  anchor_date: string;
  counted_matches: number;
}
