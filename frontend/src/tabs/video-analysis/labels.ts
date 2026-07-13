import type { Aspect, Polarity, Setting, SkillStatus } from "./types";

export const SETTING_LABEL: Record<Setting, string> = {
  practice: "Tập luyện",
  match: "Thi đấu",
};

export const ASPECT_LABEL: Record<Aspect, string> = {
  serve: "Giao bóng",
  receive: "Đỡ giao bóng",
  forehand: "Thuận tay (FH)",
  backhand: "Trái tay (BH)",
  footwork: "Bộ chân",
  stance_posture: "Tư thế / thân người",
  tactics: "Chiến thuật",
  mental: "Tâm lý",
  physical: "Thể lực",
  other: "Khác",
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
  strength: "Điểm mạnh",
  weakness: "Điểm yếu",
  neutral: "Chưa quan sát",
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
  strength: "Điểm mạnh",
  weakness: "Điểm yếu",
  improving: "Đang tiến bộ",
  needs_work: "Cần cải thiện",
  neutral: "Chưa rõ",
};

