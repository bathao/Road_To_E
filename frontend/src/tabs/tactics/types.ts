// Hand-written mirrors of backend/app/features/tactics/schemas.py — only the
// fields this tab reads (schema.d.ts is the generated drift-check artifact).

export type FactKind = "strength" | "weakness" | "style" | "note";
export type FactSubject = "me" | "opponent";

// One person the user has actually played against (the picker).
export interface Opponent {
  id: number;
  name: string;
  points: number | null;
  plays_pips: boolean;
  matches_vs: number;
  wins: number; // decided matches only
  losses: number;
  last_vs: string | null; // YYYY-MM-DD
}

// One scouting fact. player_id null = about ME (global across opponents —
// the coach never re-asks these).
export interface Fact {
  id: number;
  player_id: number | null;
  kind: FactKind;
  text: string;
  source: string; // user | interview | intake
  // Canonical intake slot ('grip', 'style', …); null = free-form fact. The
  // intake card shows a question only while its key has no fact.
  key: string | null;
}

export interface FactsOut {
  me: Fact[];
  opponent: Fact[];
}

export interface InterviewQuestion {
  subject: FactSubject;
  kind: FactKind;
  question: string;
}

export interface InterviewOut {
  model: string;
  questions: InterviewQuestion[];
}

export interface AnswerIn {
  subject: FactSubject;
  kind: FactKind;
  question: string;
  answer: string;
}

// The generated game plan (Vietnamese coach content).
export interface TacticPlan {
  id: number;
  created_at: string | null;
  player_id: number;
  model: string;
  status: "empty" | "generating" | "done" | "error";
  error_msg: string | null;
  headline: string;
  overall: string;
  serve_receive: string[];
  rally: string[];
  avoid: string[];
  mental: string[];
  data_gaps: string[];
}

// ---------------------------------------------------------------- match log
// Point-by-point charting (2026-10-10). Codes mirror vocab.ts.
import type { Ball, Place, Side, Stroke } from "./vocab";

export interface Serve {
  id: number;
  name: string;
  stance: string | null;
  motion: string | null;
  spin: string;
  amount: string | null;
  length: string;
  place: Place | null; // default landing spot (receiver's side)
  sort_order: number;
}

export type ServeIn = Omit<Serve, "id" | "sort_order">;

export interface Shot {
  h: Side;
  serve?: boolean;
  serve_id?: number | null;
  stance?: string | null;
  motion?: string | null;
  spin?: string | null;
  amount?: string | null;
  length?: string | null;
  stroke?: Stroke | null;
  ball?: Ball | null; // incoming ball (optional detail)
  place: Place | null; // null only on a shot that missed
}

export interface PointIn {
  set_no: number;
  server: Side;
  shots: Shot[];
  end_kind: "winner" | "error";
  forced: boolean;
  note: string | null;
}

export interface Point extends PointIn {
  id: number;
  match_id: number;
  point_no: number;
  winner: Side;
}

export interface SetScore {
  set_no: number;
  my_points: number | null;
  opp_points: number | null;
  first_server: Side | null;
}

export interface OppServeSeen {
  stance: string | null;
  motion: string | null;
  spin: string | null;
  amount: string | null;
  length: string | null;
  count: number;
}

export interface MatchLog {
  match_id: number;
  sets: SetScore[];
  points: Point[];
  opp_serves_seen: OppServeSeen[];
}

export interface MatchLogStatus {
  match_id: number;
  points: number;
  sets_typed: number;
}

export interface ServeStat {
  side: Side;
  serve_id: number | null;
  stance: string | null;
  motion: string | null;
  spin: string | null;
  amount: string | null;
  length: string | null;
  place: Place | null;
  played: number;
  won: number; // by the server
}

export interface PointNote {
  match_id: number;
  date: string | null;
  set_no: number;
  point_no: number;
  score: string;
  note: string;
}

export interface Stats {
  matches: number;
  points: number;
  points_me: number;
  points_opp: number;
  on_my_serve: [number, number]; // [played, won by me]
  on_opp_serve: [number, number];
  attacks: Record<string, Record<string, [number, number, number]>>; // stroke → place → [won, lost, missed]
  errors_me: Record<string, [number, number]>; // stroke → [unforced, forced]
  errors_opp: Record<string, [number, number]>;
  winners_me: Record<string, number>;
  winners_opp: Record<string, number>;
  receive_me: Record<string, [number, number, number]>; // stroke → [won, lost, missed]
  receive_opp: Record<string, [number, number, number]>;
  serves: ServeStat[];
  rally_len: Record<string, [number, number]>; // bucket → [me, opp]
  clutch: [number, number];
  notes: PointNote[];
}
