// Match line-up wording shared across tabs.

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
