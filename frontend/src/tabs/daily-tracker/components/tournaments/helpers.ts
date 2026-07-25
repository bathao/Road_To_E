// Shared countdown/label logic for the tournament strip + section.
import { fromIso, todayIso } from "../../../../shared/dates";
import type { Tournament, TournamentEntry } from "../../types";

const DAY_MS = 86_400_000;

/** Whole days from today until the tournament starts (0 = today, <0 = started). */
export function daysUntil(t: Tournament): number {
  return Math.round(
    (fromIso(t.start_date).getTime() - fromIso(todayIso()).getTime()) / DAY_MS
  );
}

/** Ended before today (end_date falls back to start_date). */
export function isPast(t: Tournament): boolean {
  return (t.end_date ?? t.start_date) < todayIso();
}

export function countdownText(t: Tournament): string {
  if (isPast(t)) return "đã đấu";
  const d = daysUntil(t);
  if (d <= 0) return d === 0 ? "HÔM NAY" : "ĐANG DIỄN RA";
  return `còn ${d} ngày`;
}

const DISCIPLINE_VI: Record<string, string> = {
  singles: "Đơn",
  doubles: "Đôi",
  team: "Đồng đội",
};

export function entryLabel(e: TournamentEntry): string {
  let label = DISCIPLINE_VI[e.discipline] ?? e.discipline;
  if (e.discipline === "doubles" && e.partner_name) label += ` — với ${e.partner_name}`;
  if (e.discipline === "team") {
    // Team name/note and the picked roster, whichever exist.
    const roster = (e.teammate_names ?? []).join(", ");
    const parts = [e.team_members, roster].filter(Boolean);
    if (parts.length) label += ` — ${parts.join(" · ")}`;
  }
  if (e.division) label += ` (${e.division})`;
  return label;
}
