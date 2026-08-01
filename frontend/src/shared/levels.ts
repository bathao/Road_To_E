// Opponent skill level relative to the user — DERIVED server-side from the
// opponent's points vs my dynamic ELO since 2026-07-27 (the hand-picked
// label is retired; the DB column is frozen legacy). "unrated" = the player
// has no points yet — never a statement about their skill.
export type PlayerLevel = "below" | "equal" | "above" | "unrated";

const SHORT: Record<PlayerLevel, string> = {
  below: "Below",
  equal: "Equal",
  above: "Above",
  unrated: "unranked",
};

export function levelShort(level: PlayerLevel | null | undefined): string {
  return level ? SHORT[level] ?? "" : "";
}
