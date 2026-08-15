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
  source: string; // user | interview
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
