// Fixed scouting-intake catalogs (2026-08-17). Each item is one canonical
// question slot: answered once, stored as a keyed fact (backend upserts on
// (player_id, key)), and the card only ever shows the still-missing keys —
// that is the "ask once, only fill what's missing" contract. The dynamic
// stuff a form can't ask (loss scenarios, serve reads, placement habits)
// stays with the LLM interview. Keys mirror ME_INTAKE_KEYS/OPP_INTAKE_KEYS
// in backend/app/features/tactics/prompt.py — keep in sync.
import type { FactKind } from "./types";

// GUI shows the English label; the stored fact text carries the Vietnamese
// gloss so the (Vietnamese-prompted) coach model reads it natively.
export interface IntakeChoice {
  en: string;
  vi?: string;
}

export interface IntakeItem {
  key: string;
  kind: FactKind;
  label: string; // English GUI label, doubles as the fact-text prefix
  choices?: IntakeChoice[]; // tap-to-answer; absent = free-text input
  placeholder?: string;
  // Offers "Not sure…" → pick a leaning or "No idea" (user 2026-08-17: some
  // answers aren't formed yet — own style is still developing, opponents may
  // be under-observed). Off for own equipment (you know your own racket).
  unsure?: boolean;
}

const RUBBERS: IntakeChoice[] = [
  { en: "Inverted", vi: "mặt láng" },
  { en: "Short pips", vi: "gai ngắn" },
  { en: "Long pips", vi: "gai dài" },
  { en: "Anti", vi: "phản xoáy" },
];

export const ME_INTAKE: IntakeItem[] = [
  {
    key: "grip",
    kind: "style",
    label: "Grip",
    choices: [
      { en: "Shakehand", vi: "vợt ngang" },
      { en: "Penhold", vi: "vợt dọc" },
    ],
  },
  {
    key: "hand",
    kind: "style",
    label: "Hand",
    choices: [
      { en: "Right", vi: "tay phải" },
      { en: "Left", vi: "tay trái" },
    ],
  },
  { key: "fh_rubber", kind: "style", label: "FH rubber", choices: RUBBERS },
  { key: "bh_rubber", kind: "style", label: "BH rubber", choices: RUBBERS },
  {
    key: "style",
    kind: "style",
    label: "Playing style",
    unsure: true,
    choices: [
      { en: "Close-table attacker", vi: "ôm bàn tấn công" },
      { en: "Block & counter", vi: "chặn đẩy phản công" },
      { en: "Chopper", vi: "cắt thủ xa bàn" },
      { en: "All-round", vi: "toàn diện" },
    ],
  },
  {
    key: "spin_speed",
    kind: "style",
    label: "Spin or speed",
    unsure: true,
    choices: [
      { en: "Spin-first", vi: "thiên xoáy" },
      { en: "Speed-first", vi: "thiên tốc độ" },
      { en: "Balanced", vi: "cân bằng" },
    ],
  },
  {
    key: "best_shot",
    kind: "strength",
    label: "Best scoring shot",
    placeholder: "The shot you trust for the point…",
  },
  {
    key: "worst_shot",
    kind: "weakness",
    label: "Weakest situation",
    placeholder: "What you fear or miss most…",
  },
];

export const OPP_INTAKE: IntakeItem[] = [
  {
    key: "hand",
    kind: "style",
    label: "Hand",
    unsure: true,
    choices: [
      { en: "Right", vi: "tay phải" },
      { en: "Left", vi: "tay trái" },
    ],
  },
  {
    key: "grip",
    kind: "style",
    label: "Grip",
    unsure: true,
    choices: [
      { en: "Shakehand", vi: "vợt ngang" },
      { en: "Penhold", vi: "vợt dọc" },
    ],
  },
  { key: "rubber", kind: "style", label: "Rubber", unsure: true, choices: RUBBERS },
  {
    key: "style",
    kind: "style",
    label: "Style",
    unsure: true,
    choices: [
      { en: "Attacker", vi: "tấn công" },
      { en: "Wall blocker", vi: "chặn đẩy thủ chắc" },
      { en: "Tricky placer", vi: "gài bóng khó" },
      { en: "Chopper", vi: "cắt thủ" },
    ],
  },
  {
    key: "weapon",
    kind: "strength",
    label: "Scariest weapon",
    placeholder: "Their shot you fear most…",
  },
  {
    key: "weak_spot",
    kind: "weakness",
    label: "Where they miss",
    placeholder: "Situations where they break down…",
  },
  {
    key: "footwork",
    kind: "note",
    label: "Footwork vs mine",
    unsure: true,
    choices: [
      { en: "They're faster", vi: "họ nhanh hơn" },
      { en: "I'm faster", vi: "tôi nhanh hơn" },
      { en: "Similar", vi: "ngang nhau" },
    ],
  },
  {
    key: "clutch",
    kind: "note",
    label: "At 8-8 / 9-9",
    unsure: true,
    choices: [
      { en: "Holds nerve", vi: "bản lĩnh" },
      { en: "Gets shaky", vi: "hay run" },
    ],
  },
];

// "Grip: Shakehand (vợt ngang)" / "Best scoring shot: <typed answer>".
export function intakeFactText(item: IntakeItem, answer: string | IntakeChoice): string {
  if (typeof answer === "string") return `${item.label}: ${answer}`;
  return `${item.label}: ${answer.en}${answer.vi ? ` (${answer.vi})` : ""}`;
}

// Unsure answers still fill the slot (the form must not nag someone who
// genuinely doesn't know) — the coach reads "chưa rõ/chưa chắc" as honest
// uncertainty, and the interview may revisit OPPONENT unknowns after new
// matches (prompt rule).
export function intakeUnsureText(item: IntakeItem, leaning?: IntakeChoice): string {
  if (leaning) {
    const vi = leaning.vi ? `hơi thiên ${leaning.vi}, chưa chắc` : "chưa chắc";
    return `${item.label}: leaning ${leaning.en} — not sure yet (${vi})`;
  }
  return `${item.label}: not sure yet (chưa rõ)`;
}
