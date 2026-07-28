import type { Aspect, Polarity, Setting, SkillStatus } from "./types";

export const SETTING_LABEL: Record<Setting, string> = {
  practice: "Practice",
  match: "Match",
};

export const ASPECT_LABEL: Record<Aspect, string> = {
  serve: "Serve",
  receive: "Serve return",
  forehand: "Forehand (FH)",
  backhand: "Backhand (BH)",
  footwork: "Footwork",
  stance_posture: "Stance / posture",
  tactics: "Tactics",
  mental: "Mentality",
  physical: "Fitness",
  other: "Other",
};

export const ASPECT_ORDER: Aspect[] = [
  "serve",
  "receive",
  "forehand",
  "backhand",
  "footwork",
  "stance_posture",
  "tactics",
  "mental",
  "physical",
  "other",
];

export const POLARITY_LABEL: Record<Polarity, string> = {
  strength: "Strength",
  weakness: "Weakness",
  neutral: "Not observed",
};

// CSS class per skill status (shared by SkillBoard + the Profile tab).
export const SKILL_STATUS_CLASS: Record<SkillStatus, string> = {
  strength: "va-sk-strong",
  improving: "va-sk-improving",
  neutral: "va-sk-neutral",
  needs_work: "va-sk-needswork",
  weakness: "va-sk-weak",
};

export const SKILL_STATUS_LABEL: Record<SkillStatus, string> = {
  strength: "Strength",
  weakness: "Weakness",
  improving: "Improving",
  needs_work: "Needs work",
  neutral: "Unclear",
};

