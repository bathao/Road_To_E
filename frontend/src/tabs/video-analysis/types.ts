export type ClipType = "training" | "match_points";
export type Status =
  | "pending"
  | "processing"
  | "awaiting_confirm"
  | "needs_id"
  | "analyzing"
  | "done"
  | "error";
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

export interface Trait {
  id: number;
  aspect: Aspect;
  polarity: Polarity;
  text: string;
  confidence: number | null;
  source_clip_id: number | null;
  created_at: string;
}

export interface TraitIn {
  aspect: Aspect;
  polarity: Polarity;
  text: string;
  confidence?: number | null;
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
