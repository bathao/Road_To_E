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

/** Played = backend flag: ended before today OR results already entered —
 * inputting a same-day tournament's results retires its card immediately. */
export function isPast(t: Tournament): boolean {
  return t.played;
}

// Only upcoming tournaments render a countdown — played ones left the
// Daily Tracker for the Profile Tournament Record (2026-08-01).
export function countdownText(t: Tournament): string {
  const d = daysUntil(t);
  if (d <= 0) return d === 0 ? "TODAY" : "ONGOING";
  return `${d} days left`;
}
