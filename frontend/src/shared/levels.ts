// Opponent skill level relative to the user — DERIVED server-side from the
// opponent's points vs my dynamic ELO since 2026-07-27 (the hand-picked
// label is retired; the DB column is frozen legacy). "unrated" = the player
// has no points yet — never a statement about their skill.
export type PlayerLevel = "below" | "equal" | "above" | "unrated";

export const LEVELS: { key: PlayerLevel; label: string; short: string }[] = [
  { key: "below", label: "Below me", short: "Below" },
  { key: "equal", label: "Equal", short: "Equal" },
  { key: "above", label: "Above me", short: "Above" },
  { key: "unrated", label: "Unrated", short: "unranked" },
];

export function levelShort(level: PlayerLevel | null | undefined): string {
  return LEVELS.find((l) => l.key === level)?.short ?? "";
}

export function levelLabel(level: PlayerLevel | null | undefined): string {
  return LEVELS.find((l) => l.key === level)?.label ?? "";
}
