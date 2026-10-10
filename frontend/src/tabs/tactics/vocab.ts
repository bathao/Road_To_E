// Match-log vocabulary: the fixed English codes the backend stores
// (backend/app/features/tactics/models.py) and their chip labels. The
// table-tennis terms are Vietnamese by the user's explicit request
// (2026-10-10: "kiểu giao bóng, các cú đánh … có thể ghi tiếng việt được,
// cho thân thiện") — a standing exception to the English-GUI rule; the
// surrounding chrome stays English.

export type Side = "me" | "opp";
export type Place = "R" | "M" | "L";

export interface Choice<C extends string = string> {
  code: C;
  label: string;
  key: string; // keyboard shortcut shown on the chip
}

const list = <C extends string>(rows: [C, string, string][]): Choice<C>[] =>
  rows.map(([code, label, key]) => ({ code, label, key }));

export const STANCES = list([
  ["right", "Đứng lệch phải", "1"],
  ["center", "Đứng giữa bàn", "2"],
  ["left", "Đứng lệch trái", "3"],
] as ["right" | "center" | "left", string, string][]);

export const MOTIONS = list([
  ["pend", "Thuận tay (pendulum)", "1"],
  ["rev", "Ngược (reverse)", "2"],
  ["bh", "Trái tay", "3"],
  ["toma", "Búa (tomahawk)", "4"],
  ["other", "Khác", "5"],
] as ["pend" | "rev" | "bh" | "toma" | "other", string, string][]);

export const SPINS = list([
  ["back", "Xoáy xuống", "1"],
  ["side", "Xoáy ngang", "2"],
  ["sideback", "Ngang-xuống", "3"],
  ["top", "Xoáy lên", "4"],
  ["none", "Lỏng / không xoáy", "5"],
] as ["back" | "side" | "sideback" | "top" | "none", string, string][]);

export const AMOUNTS = list([
  ["light", "Nhẹ", "1"],
  ["med", "Vừa", "2"],
  ["heavy", "Nặng", "3"],
] as ["light" | "med" | "heavy", string, string][]);

export const LENGTHS = list([
  ["short", "Ngắn", "1"],
  ["half", "Nửa bàn", "2"],
  ["long", "Dài", "3"],
] as ["short" | "half" | "long", string, string][]);

export const PLACES: Choice<Place>[] = list([
  ["R", "Phải", "R"],
  ["M", "Giữa", "M"],
  ["L", "Trái", "L"],
] as [Place, string, string][]);

export type Stroke =
  | "fhloop" | "bhloop" | "fhdrive" | "bhdrive" | "fhpush" | "bhpush"
  | "flick" | "block" | "smash" | "chop" | "other";

export const STROKES: Choice<Stroke>[] = list([
  ["fhloop", "Giật phải", "1"],
  ["bhloop", "Giật trái", "2"],
  ["fhdrive", "Bạt phải", "3"],
  ["bhdrive", "Bạt trái", "4"],
  ["fhpush", "Gò phải", "5"],
  ["bhpush", "Gò trái", "6"],
  ["flick", "Hất", "7"],
  ["block", "Chặn", "8"],
  ["smash", "Đập", "9"],
  ["chop", "Thủ / lốp", "0"],
  ["other", "Đỡ / cú khác", "."],
] as [Stroke, string, string][]);

// Optional: the incoming ball a stroke was played against.
export type Ball = "back" | "top" | "none";
export const BALLS: Choice<Ball>[] = list([
  ["back", "Bóng xoáy xuống", "B"],
  ["top", "Bóng xoáy lên", "T"],
  ["none", "Bóng lỏng", "N"],
] as [Ball, string, string][]);

// Landing-spot label; a shot that missed has none.
export const placeLabel = (p: Place | null | undefined) => (p ? labelOf(PLACES, p) : "hỏng");

export const ATTACK_STROKES: ReadonlySet<string> = new Set([
  "fhloop", "bhloop", "fhdrive", "bhdrive", "smash", "flick",
]);

export function labelOf(choices: Choice[], code: string | null | undefined): string {
  if (!code) return "";
  return choices.find((c) => c.code === code)?.label ?? code;
}

// Compact description of a serve's attributes: "Thuận tay · xoáy xuống nặng · ngắn".
export function serveDesc(s: {
  stance?: string | null;
  motion?: string | null;
  spin?: string | null;
  amount?: string | null;
  length?: string | null;
}): string {
  const spin = [labelOf(SPINS, s.spin), labelOf(AMOUNTS, s.amount).toLowerCase()]
    .filter(Boolean)
    .join(" ");
  return [labelOf(STANCES, s.stance), labelOf(MOTIONS, s.motion), spin, labelOf(LENGTHS, s.length)]
    .filter(Boolean)
    .join(" · ");
}

export const RALLY_BUCKETS: [string, string][] = [
  ["1-2", "1–2 cú"],
  ["3-4", "3–4 cú"],
  ["5+", "5+ cú"],
];
