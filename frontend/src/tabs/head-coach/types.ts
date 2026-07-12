// Mirrors backend app/features/head_coach/schemas.py

export interface Priority {
  title: string;
  why: string;
  source: string;
}

export interface Directive {
  area: string; // training | playing_hours | matches | skill | tactics | recovery
  order: string;
  target: string;
  reason: string;
}

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

export interface SourceVideo {
  player?: string;
  reports_reviewed?: number;
  findings_accepted?: number;
  [k: string]: unknown;
}

export interface SourceTraining {
  level?: string;
  sessions_last_7d?: number;
  total_sessions_done?: number;
  [k: string]: unknown;
}

export interface SourceSummary {
  video: SourceVideo;
  training: SourceTraining;
  match: SourceMatch;
  tactics: Record<string, unknown>;
  generated_for_range: string;
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
