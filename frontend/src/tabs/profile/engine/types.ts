export type Polarity = "strength" | "weakness" | "neutral";
// Footage setting: practice/warm-up vs real competitive match.
export type Setting = "practice" | "match";
export type Aspect =
  | "serve"
  | "receive"
  | "forehand"
  | "backhand"
  | "footwork"
  | "stance_posture"
  | "tactics"
  | "mental"
  | "physical"
  | "other";

export interface Profile {
  id: number;
  name: string;
  handed: string;
  grip: string;
  style: string;
  equipment: string;
  physique: string;
  serve_summary: string;
  footwork_summary: string;
  posture_summary: string;
  strengths_summary: string;
  weaknesses_summary: string;
  overall_summary: string;
  updated_at: string;
}

export type ProfileIn = Partial<Omit<Profile, "id" | "updated_at">>;

export type FindingStatus = "proposed" | "accepted" | "rejected";

export interface Trait {
  id: number;
  aspect: Aspect;
  polarity: Polarity;
  text: string;
  ai_text: string | null;
  confidence: number | null;
  status: FindingStatus;
  source_report_id: number | null;
  created_at: string;
}

export interface TraitIn {
  aspect: Aspect;
  polarity: Polarity;
  text: string;
  confidence?: number | null;
}

export type SkillStatus =
  | "strength"
  | "weakness"
  | "improving"
  | "needs_work"
  | "neutral";

export interface Skill {
  id: number;
  aspect: Aspect;
  setting: Setting;
  rating: number | null;
  status: SkillStatus;
  assessment: string;
  priority: number | null;
  updated_at: string;
}

export interface SkillIn {
  rating?: number | null;
  status?: SkillStatus;
  assessment?: string;
  priority?: number | null;
}

export interface SkillReportItem {
  aspect: Aspect;
  setting: Setting;
  rating: number | null;
  status: SkillStatus;
  assessment: string;
  priority: number | null;
  evidence: string[];
}

// Development over time.
export interface SkillPoint {
  analysis_date: string; // ISO date
  rating: number | null;
  status: SkillStatus;
}
export interface SkillHistory {
  aspect: Aspect;
  setting: Setting;
  points: SkillPoint[];
}
export interface FindingPoint {
  analysis_date: string;
  aspect: Aspect;
  polarity: Polarity;
  text: string;
  setting: Setting;
}

export interface AspectSettingStat {
  aspect: Aspect;
  practice_strengths: number;
  practice_weaknesses: number;
  match_strengths: number;
  match_weaknesses: number;
  practice_samples: string[];
  match_samples: string[];
}

export interface Report {
  name: string;
  handed: string;
  grip: string;
  style: string;
  overall_summary: string;
  skills: SkillReportItem[];
  strengths: string[];
  weaknesses: string[];
  improvement_priorities: string[];
  skill_history: SkillHistory[];
  findings_timeline: FindingPoint[];
  practice_vs_match: AspectSettingStat[];
  reports_reviewed: number;
  findings_accepted: number;
}

