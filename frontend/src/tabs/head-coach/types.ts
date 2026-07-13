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
  unit_vi: string; // buổi | giờ | trận
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
  practice?: SourceMatchSide;
  official?: SourceMatchSide;
  trend_by_month?: { label?: string; played?: number; win_rate?: number | null }[];
  top_h2h?: SourceH2H[];
  [k: string]: unknown;
}

export interface SourceNote {
  date?: string;
  text?: string;
}

export interface SourceSummary {
  player?: string;
  training: SourceTraining;
  match: SourceMatch;
  match_detail?: SourceMatchDetail;
  notes?: SourceNote[];
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
