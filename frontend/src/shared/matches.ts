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

// The knockout ladder. Group → first knockout round stays a MANUAL pick
// (the app can't know the bracket size), and winning the Final has nowhere
// further to go — both map to themselves via the ?? fallback.
const NEXT_ROUND: Partial<Record<TournamentRound, TournamentRound>> = {
  r64: "r32",
  r32: "r16",
  r16: "r8",
  r8: "qf",
  qf: "sf",
  sf: "f",
};

export function nextRound(r: TournamentRound): TournamentRound {
  return NEXT_ROUND[r] ?? r;
}

// "give 2-0-2" / "receive 4" — one handicap phrasing for every list row
// (MatchEditor, MatchRowList, Profile drill-down, h2h MatchLines). Non-uniform
// ratios show the per-set sequence; null = no handicap.
export function hdcLabel(
  handicap: number,
  pattern?: string | null
): string | null {
  if (handicap === 0) return null;
  const amount = pattern ?? String(Math.abs(handicap));
  return `${handicap > 0 ? "give" : "receive"} ${amount}`;
}

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
