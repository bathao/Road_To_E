// Tournament display helpers shared by the Daily Tracker (planning cards +
// strip) and the Profile tab's Tournament Record (read-only history).

// Final results, DERIVED by the backend from the entered matches' rounds
// (never input). "3rd (lost SF)" — all bronze is shared, no 3rd-place match;
// "Quarter-final" (lost the QF) is a singles-only bonus tier.
export const PLACEMENT_LABEL: Record<string, string> = {
  champion: "🥇 Champion",
  runner_up: "🥈 Runner-up",
  third: "🥉 3rd (lost SF)",
  quarterfinal: "Quarter-final",
};

// Competition format (2026-09-25). knockout = the classic tournament (group
// stage → knockout ladder: rounds, ☠ knocked-out, derived placements);
// league = a fixed round-robin block of 3–5 matches and done — no rounds,
// no elimination, no placement, W–L is the whole result ("BBTV League").
export const TOURNAMENT_FORMATS: [string, string][] = [
  ["knockout", "Tournament"],
  ["league", "League"],
];
export const isLeague = (t: { format?: string | null }) => t.format === "league";
/** Card / strip / banner icon by format. */
export const tournamentIcon = (t: { format?: string | null }) =>
  isLeague(t) ? "🎽" : "🏆";

// Tournament entry disciplines — the single source for both the entry form
// (TournamentSection) and every label rendered from an entry.
export const TOURNAMENT_DISCIPLINES: [string, string][] = [
  ["singles", "Singles"],
  ["doubles", "Doubles"],
  ["team", "Team"],
];
const DISCIPLINE_LABEL: Record<string, string> = Object.fromEntries(
  TOURNAMENT_DISCIPLINES
);

// Structurally typed so both tabs' entry shapes fit (the Daily Tracker's
// TournamentEntry and the record endpoint's EntryOut both carry these slots).
export function entryLabel(e: {
  discipline: string;
  partner_name?: string | null;
  teammate_names?: string[];
  team_members?: string | null;
  division?: string | null;
}): string {
  let label = DISCIPLINE_LABEL[e.discipline] ?? e.discipline;
  if (e.discipline === "doubles" && e.partner_name) label += ` — with ${e.partner_name}`;
  if (e.discipline === "team") {
    // Team name/note and the picked roster, whichever exist.
    const roster = (e.teammate_names ?? []).join(", ");
    const parts = [e.team_members, roster].filter(Boolean);
    if (parts.length) label += ` — ${parts.join(" · ")}`;
  }
  if (e.division) label += ` (${e.division})`;
  return label;
}
