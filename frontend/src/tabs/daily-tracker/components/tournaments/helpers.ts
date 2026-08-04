// Shared countdown/label logic for the tournament strip + section.
// entryLabel (+ PLACEMENT_LABEL, now Profile-only) moved to
// shared/tournaments.ts 2026-08-01 — re-exported so the strip/section keep
// their one import path.
import { fromIso, todayIso } from "../../../../shared/dates";
import type { Tournament } from "../../types";

export { entryLabel } from "../../../../shared/tournaments";

const DAY_MS = 86_400_000;

/** Whole days from today until the tournament starts (0 = today, <0 = started). */
export function daysUntil(t: Tournament): number {
  return Math.round(
    (fromIso(t.start_date).getTime() - fromIso(todayIso()).getTime()) / DAY_MS
  );
}

/** Played = backend flag: past the tournament's LAST day, or results
 * entered for that last day. Same-day results still retire a single-day
 * card immediately; a multi-day card survives day-1 results (2026-08-04). */
export function isPast(t: Tournament): boolean {
  return t.played;
}

// Only upcoming tournaments render a countdown — played ones left the
// Daily Tracker for the Profile Tournament Record (2026-08-01).
export function countdownText(t: Tournament): string {
  const d = daysUntil(t);
  if (d > 0) return `${d} days left`;
  // Running now. Multi-day events show which day of the event it is
  // ("TODAY · day 2/2") — the plain start-based countdown read wrong from
  // day 2 on.
  const end = t.end_date ?? t.start_date;
  const total =
    Math.round(
      (fromIso(end).getTime() - fromIso(t.start_date).getTime()) / DAY_MS
    ) + 1;
  if (total > 1 && 1 - d <= total) return `TODAY · day ${1 - d}/${total}`;
  return d === 0 ? "TODAY" : "ONGOING";
}
