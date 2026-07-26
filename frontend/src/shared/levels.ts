// Opponent skill level relative to the user — DERIVED server-side from the
// opponent's points vs my dynamic ELO since 2026-07-27 (the hand-picked
// label is retired; the DB column is frozen legacy). "unrated" = the player
// has no points yet — never a statement about their skill.
export type PlayerLevel = "below" | "equal" | "above" | "unrated";

export const LEVELS: { key: PlayerLevel; label: string; short: string }[] = [
  { key: "below", label: "Dưới tôi", short: "Dưới" },
  { key: "equal", label: "Ngang tôi", short: "Ngang" },
  { key: "above", label: "Hơn tôi", short: "Hơn" },
  { key: "unrated", label: "Chưa có điểm", short: "chưa xếp" },
];

export function levelShort(level: PlayerLevel | null | undefined): string {
  return LEVELS.find((l) => l.key === level)?.short ?? "";
}

export function levelLabel(level: PlayerLevel | null | undefined): string {
  return LEVELS.find((l) => l.key === level)?.label ?? "";
}
