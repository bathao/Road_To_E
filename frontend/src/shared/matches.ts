// Match line-up wording + tournament-round labels shared across tabs.

/** Tournament round of a match. Group stage is the bulk; knockout rounds
 * run 1/64 → Final, entered only as far as the player survives. */
export type TournamentRound =
  | "group"
  | "r64"
  | "r32"
  | "r16"
  | "r8"
  | "qf"
  | "sf"
  | "f";

export const ROUND_LABEL: Record<TournamentRound, string> = {
  group: "Group",
  r64: "1/64",
  r32: "1/32",
  r16: "1/16",
  r8: "1/8",
  qf: "Quarter-final",
  sf: "Semi-final",
  f: "Final",
};

// Compact chip labels; group stage stays blank (it's the default bulk —
// only knockout rounds earn a tag).
export const ROUND_SHORT: Record<TournamentRound, string> = {
  group: "",
  r64: "1/64",
  r32: "1/32",
  r16: "1/16",
  r8: "1/8",
  qf: "QF",
  sf: "SF",
  f: "F",
};

// "with <partner> vs <opponents>" — mirrors the MatchEditor list wording.
// Structurally typed so anything carrying the name slots can use it (Match
// rows in the drill-down modals, RatingMover rows in the Profile ELO table).
export function matchupOf(m: {
  discipline: string;
  opponent_name?: string | null;
  opponent2_name?: string | null;
  partner_name?: string | null;
}): string {
  const opp1 = m.opponent_name ?? "?";
  const opps =
    m.discipline === "doubles" || m.discipline === "one_v_two"
      ? `${opp1} + ${m.opponent2_name ?? "?"}`
      : opp1;
  const partner =
    m.discipline === "doubles" || m.discipline === "two_v_one"
      ? m.partner_name ?? "?"
      : null;
  return partner ? `with ${partner} vs ${opps}` : `vs ${opps}`;
}
