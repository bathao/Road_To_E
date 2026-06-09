import type {
  Aspect,
  ClipType,
  FindingStatus,
  Focus,
  Polarity,
  Side,
  SkillStatus,
} from "./types";

export const SIDE_LABEL: Record<Side, string> = {
  "": "— Chưa rõ —",
  left: "Bên trái",
  right: "Bên phải",
  top: "Phía trên (xa camera)",
  bottom: "Phía dưới (gần camera)",
  alone: "Một mình (clip tập)",
};

export const SIDE_ORDER: Side[] = ["", "left", "right", "bottom", "top", "alone"];

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
  neutral: "Trung tính",
};

export const CLIP_TYPE_LABEL: Record<ClipType, string> = {
  training: "Clip tập",
  match_points: "Điểm trong trận",
};

// Drill focus — what the AI should concentrate its analysis on.
export const FOCUS_LABEL: Record<Focus, string> = {
  "": "— Tổng quát —",
  serve_practice: "Tập giao bóng",
  footwork_drill: "Tập bộ chân",
  rally: "Bóng qua lại (rally)",
  match: "Điểm trận đấu",
  free: "Tự do / tổng quát",
};

export const FOCUS_ORDER: Focus[] = [
  "",
  "serve_practice",
  "footwork_drill",
  "rally",
  "match",
];

export const STATUS_LABEL: Record<string, string> = {
  pending: "Chờ xử lý",
  processing: "Đang nhận diện…",
  awaiting_confirm: "Chờ bạn xác nhận",
  needs_id: "Cần thông tin",
  analyzing: "Đang phân tích…",
  done: "Xong",
  error: "Lỗi",
  stopped: "Đã dừng",
};

export const SKILL_STATUS_LABEL: Record<SkillStatus, string> = {
  strength: "Điểm mạnh",
  weakness: "Điểm yếu",
  improving: "Đang tiến bộ",
  needs_work: "Cần cải thiện",
  neutral: "Chưa rõ",
};

export const FINDING_STATUS_LABEL: Record<FindingStatus, string> = {
  proposed: "Chờ duyệt",
  accepted: "Đã duyệt",
  rejected: "Đã bỏ",
};
