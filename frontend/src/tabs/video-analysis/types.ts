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

// A metric compared to the player's own baseline (Phase 3 progress tracking).
export interface MetricTrend {
  name: string;
  label: string;
  unit: string;
  current: number;
  baseline: number;
  delta: number;
  pct: number | null;
  better: "up" | "down" | "neutral";
  trend: "improved" | "declined" | "flat" | "changed";
  samples: number;
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
  metric_trends: MetricTrend[];
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
  serve_variety?: { notes?: string };
  tactics?: { notes?: string };
  recommendations?: string[];
  // Self-critique (Pass C) summary: how many draft findings were re-checked,
  // dropped (unsupported) and downgraded (shaky) before review.
  critique?: { reviewed: number; dropped: number; downgraded: number };
}

// Ball + table tracking (Phase 4 / NC1). Best-effort: `available` may be false.
export interface BallZone {
  zone: string;
  gx: number;
  gy: number;
  count: number;
}
export interface BallTracking {
  available?: boolean;
  method?: string;
  zones?: BallZone[];
  table?: { area_frac: number; color: string } | null;
  n_points?: number;
  mean_conf?: number;
  note?: string;
}

export interface Analysis {
  id: number;
  clip_id: number;
  model: string;
  language: string;
  summary: string;
  raw: RawAnalysis;
  pose: Record<string, unknown>;
  ball?: BallTracking;
  progress: MetricTrend[];
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

// Face/body identity enrollment (ArcFace).
export interface IdentityEnrollMeta {
  status: string; // ok | no_anchor
  anchors?: number;
  anchor_files?: number;
  kept_from_gallery?: number;
  rejected_from_gallery?: number;
  gallery_noface?: number;
  identity_face_samples?: number;
  identity_body_samples?: number;
  rejected_sample?: string[];
}

export interface IdentityStatus {
  enrolled: boolean;
  anchor_dir: string;
  anchor_files: number;
  meta?: IdentityEnrollMeta;
}

export type IdentityEnroll = IdentityEnrollMeta;
