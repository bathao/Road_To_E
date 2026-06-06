// Opponent skill level relative to the user — the single source of truth for
// the level union and its Vietnamese labels (short + long forms).
export type PlayerLevel = "below" | "equal" | "above";

export const LEVELS: { key: PlayerLevel; label: string; short: string }[] = [
  { key: "below", label: "Dưới tôi", short: "Dưới" },
  { key: "equal", label: "Ngang tôi", short: "Ngang" },
  { key: "above", label: "Hơn tôi", short: "Hơn" },
];

export function levelShort(level: PlayerLevel | null | undefined): string {
  return LEVELS.find((l) => l.key === level)?.short ?? "";
}

export function levelLabel(level: PlayerLevel | null | undefined): string {
  return LEVELS.find((l) => l.key === level)?.label ?? "";
}
