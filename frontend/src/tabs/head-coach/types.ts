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

export interface SourceSummary {
  video: Record<string, unknown>;
  training: Record<string, unknown>;
  match: Record<string, unknown>;
  tactics: Record<string, unknown>;
  generated_for_range: string;
}

export interface Assessment {
  id: number | null;
  created_at: string | null;
  model: string;
  overall_assessment: string;
  top_priorities: Priority[];
  directives: Directive[];
  tactics: TacticSuggestion[];
  week_plan: PlanDay[];
  watch_items: string[];
  sources: SourceSummary;
  empty: boolean;
}
