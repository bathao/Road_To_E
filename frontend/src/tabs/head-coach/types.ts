// Mirrors backend app/features/head_coach/schemas.py

export interface Priority {
  title: string;
  why: string;
  source: string;
}

export interface Directive {
  area: string; // training | playing_hours | matches | skill | recovery
  order: string;
  target: string;
  reason: string;
  // Weekly machine-trackable goal ("" when not quantifiable) — the app
  // computes this week's actual from the database (see DirectiveProgress).
  metric?: string;
  value?: number | null;
}

// Live progress of one trackable directive (GET /head-coach/directive-progress).
export interface DirectiveProgress {
  index: number; // position in the assessment's directives list
  area: string;
  order: string;
  metric: string;
  value: number; // weekly target
  actual: number; // this week's actual (Mon → today)
  pct: number; // 0-100
  unit_vi: string; // display unit: sessions | hours | matches
}

export interface DirectiveProgressOut {
  assessment_id: number | null;
  week_start: string | null;
  items: DirectiveProgress[];
}

// LEGACY — tactic suggestions were dropped from the verdict (the coach can't
// know what tactics the player uses); old snapshots may still carry them.
export interface TacticSuggestion {
  situation: string;
  action: string;
}

export interface PlanDay {
  day: string;
  focus: string;
  detail: string;
}

// The backend builds these dicts in head_coach/service.gather_bundle; the
// fields the UI reads are typed here (extra keys stay accessible as unknown).
export interface SourceMatchSide {
  played?: number;
  wins?: number;
  losses?: number;
  win_rate?: number | null;
}

export interface SourceMatch {
  window_days?: number;
  overall?: SourceMatchSide;
  singles?: SourceMatchSide;
  doubles?: SourceMatchSide;
  vs_pips?: SourceMatchSide;
  [k: string]: unknown;
}

export interface SourceTraining {
  level?: string;
  sessions_last_7d?: number;
  total_sessions_done?: number;
  [k: string]: unknown;
}

export interface SourceH2H {
  name?: string;
  level?: string;
  played?: number;
  wins?: number;
  losses?: number;
  win_rate?: number | null;
  last?: string;
}

export interface SourceMatchDetail {
  window?: string;
  by_level?: Record<string, SourceMatchSide>;
  practice?: SourceMatchSide; // casual
  official?: SourceMatchSide; // light stakes
  tournament?: SourceMatchSide; // tournament
  trend_by_month?: { label?: string; played?: number; win_rate?: number | null }[];
  top_h2h?: SourceH2H[];
  [k: string]: unknown;
}

export interface SourceNote {
  date?: string;
  text?: string;
}

// Coach & Recap items fed to the coach (tags carry display labels).
export interface SourceSessionNote {
  date?: string;
  text?: string;
  tags?: string[];
}

export interface SourceSummary {
  player?: string;
  training: SourceTraining;
  match: SourceMatch;
  match_detail?: SourceMatchDetail;
  notes?: SourceNote[];
  coach_advice?: SourceSessionNote[]; // real-life coach's still-open advice
  session_recaps?: SourceSessionNote[]; // recent coach-session recaps
  generated_for_range: string;
  // Legacy fields — only present on snapshots generated before the
  // technique-analysis and playbook tabs were retired.
  video?: Record<string, unknown>;
  tactics?: Record<string, unknown>;
}

export interface Assessment {
  id: number | null;
  created_at: string | null;
  model: string;
  status: "generating" | "done" | "error";
  error_msg: string | null;
  overall_assessment: string;
  top_priorities: Priority[];
  directives: Directive[];
  tactics: TacticSuggestion[];
  week_plan: PlanDay[];
  watch_items: string[];
  sources: SourceSummary;
  empty: boolean;
}

export interface GenerateStatus {
  id: number | null;
  status: "none" | "generating" | "done" | "error";
  error_msg: string | null;
}

// ------------------------------------------------------ weekly/monthly recap
// week = the last 7 days, month = the last 30 days — rolling windows ending
// the day the Generate button is pressed. Button-only, nothing automatic.
export type RecapPeriod = "week" | "month";

// Code-computed numbers for one recap window (never from the LLM).
export interface RecapPeriodStats {
  date_from: string;
  date_to: string;
  days_trained: number;
  days_physical: number;
  physical_sessions: number;
  minutes_total: number;
  racket_minutes_total: number;
  matches_played: number;
  matches_wins: number;
  matches_losses: number;
  win_rate: number | null;
  elo_delta: number;
  elo_end: number | null; // null = period ends before the ELO anchor
  elo_counted: number;
}

export interface RecapStats {
  current: RecapPeriodStats;
  // null when the previous period predates all tracked data.
  previous: RecapPeriodStats | null;
}

export interface Recap {
  id: number;
  created_at: string | null;
  model: string;
  status: "generating" | "done" | "error";
  error_msg: string | null;
  period_type: RecapPeriod;
  period_start: string;
  period_end: string;
  headline: string;
  overall: string;
  went_well: string[];
  concerns: string[];
  focus_next: string[];
  stats: RecapStats | null;
}

// Only the most recently generated recap is surfaced (no history browsing,
// no auto-generation — the user's explicit choices, 2026-08-01).
export interface RecapsOut {
  period_type: RecapPeriod;
  latest: Recap | null;
}

// ---------------------------------------------------------------- coach chat
export interface ChatMessage {
  id: number;
  created_at: string | null;
  role: "user" | "coach";
  content: string;
  status: "pending" | "done" | "error";
  error_msg: string | null;
  model: string;
}

export interface ChatHistory {
  messages: ChatMessage[];
  // True while a coach reply is being generated (keep polling GET /chat).
  pending: boolean;
}

// ------------------------------------------------------------ coach notebook
export interface CoachNote {
  id: number;
  created_at: string | null;
  text: string;
  source: "chat" | "user"; // auto-written from chat | added by the player
}

export interface NotesOut {
  notes: CoachNote[];
}

// -------------------------------------------------------------- dev log panel
export interface OllamaModelPs {
  name: string;
  size_mb: number;
  size_vram_mb: number;
  expires_at: string;
}

export interface DebugOut {
  logs: string[];
  ollama_ok: boolean;
  ollama_error: string;
  loaded_models: OllamaModelPs[];
}
