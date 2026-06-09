export type ClipType = "training" | "match_points";
export type Focus =
  | ""
  | "serve_practice"
  | "footwork_drill"
  | "rally"
  | "match"
  | "free";
export type Status =
  | "pending"
  | "processing"
  | "awaiting_confirm"
  | "needs_id"
  | "analyzing"
  | "done"
  | "error"
  | "stopped";
export type Side = "" | "left" | "right" | "top" | "bottom" | "alone";
export type Polarity = "strength" | "weakness" | "neutral";
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
  t_ref: number | null;
  // Annotated evidence thumbnail (skeleton + joint angles) for this finding.
  evidence: { stroke_idx: number | null; t: number | null; thumb: string } | null;
  status: FindingStatus;
  source_clip_id: number | null;
  created_at: string;
}

export interface TraitIn {
  aspect: Aspect;
  polarity: Polarity;
  text: string;
  confidence?: number | null;
}

// One reviewed finding sent back to the server.
export interface FindingDecision {
  id: number;
  accept: boolean;
  text?: string;
  aspect?: Aspect;
  polarity?: Polarity;
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
  rating: number | null;
  status: SkillStatus;
  assessment: string;
  priority: number | null;
  evidence: string[];
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
  clips_reviewed: number;
  findings_accepted: number;
}

export interface ProfileImage {
  id: number;
  source_clip_id: number | null;
  created_at: string;
}

// The structured payload the VLM returns (stored in analysis.raw).
export interface RawAnalysis {
  identified?: boolean;
  confidence?: number;
  subject?: string;
  summary?: string;
  strengths?: { aspect: Aspect; text: string }[];
  weaknesses?: { aspect: Aspect; text: string }[];
  serve?: { type?: string; notes?: string };
  footwork?: { notes?: string };
  posture?: { notes?: string };
  recommendations?: string[];
  // Self-critique (Pass C) summary: how many draft findings were re-checked,
  // dropped (unsupported) and downgraded (shaky) before review.
  critique?: { reviewed: number; dropped: number; downgraded: number };
}

export interface Analysis {
  id: number;
  clip_id: number;
  model: string;
  language: string;
  summary: string;
  raw: RawAnalysis;
  pose: Record<string, unknown>;
  created_at: string;
}

export interface Clip {
  id: number;
  original_name: string;
  clip_type: ClipType;
  focus: Focus;
  title: string;
  note: string | null;
  duration_sec: number | null;
  fps: number | null;
  frames_sampled: number | null;
  width: number | null;
  height: number | null;
  model: string;
  status: Status;
  error_msg: string | null;
  created_at: string;
  processing_started_at: string | null;
  reviewed_at: string | null;
  me_side: Side;
  me_appearance: string;
  subject_desc: string | null;
  identified: boolean;
}

export interface ClipDetail extends Clip {
  analysis: Analysis | null;
  traits: Trait[];
}

export interface ModelHealth {
  ollama_up: boolean;
  models: string[];
  default_model: string;
  default_available: boolean;
  message: string;
}
