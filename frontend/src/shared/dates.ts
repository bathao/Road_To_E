// Local-date helpers. We always operate on the LOCAL calendar day (never UTC)
// so the grid matches the user's wall clock.

export function toIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function fromIso(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

// Monday of the week containing `d`.
export function mondayOf(d: Date): Date {
  const date = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const day = date.getDay(); // 0=Sun..6=Sat
  const diff = day === 0 ? -6 : 1 - day; // shift back to Monday
  date.setDate(date.getDate() + diff);
  return date;
}

export function addDays(d: Date, n: number): Date {
  const date = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  date.setDate(date.getDate() + n);
  return date;
}

export function todayIso(): string {
  return toIso(new Date());
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

// "Mon 2" for column headers.
export function dayHeader(iso: string): { weekday: string; dayNum: number } {
  const d = fromIso(iso);
  const idx = (d.getDay() + 6) % 7; // Mon=0
  return { weekday: WEEKDAYS[idx], dayNum: d.getDate() };
}

// Group a run of ISO days into consecutive month spans, for a month-grouping
// header row (e.g. the Year grid). Includes the year only when the range spans
// more than one calendar year, to keep labels short.
export function monthGroups(
  daysIso: string[]
): { label: string; span: number }[] {
  const years = new Set(daysIso.map((iso) => iso.slice(0, 4)));
  const showYear = years.size > 1;
  const groups: { label: string; span: number }[] = [];
  for (const iso of daysIso) {
    const d = fromIso(iso);
    const label = showYear
      ? `${MONTHS[d.getMonth()]} ${d.getFullYear()}`
      : MONTHS[d.getMonth()];
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.span++;
    else groups.push({ label, span: 1 });
  }
  return groups;
}

// "2 Jun 2026" for the week range label.
export function prettyDate(iso: string): string {
  const d = fromIso(iso);
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

// "2026-07-27" → "27/07" for compact chart labels.
export function shortDate(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

// "2026-07-27" → "27/07/2026".
export function dmyDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

export function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

export function endOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth() + 1, 0);
}

export function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}

// "Jun 2026" for the month label.
export function monthLabel(d: Date): string {
  return `${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function startOfYear(d: Date): Date {
  return new Date(d.getFullYear(), 0, 1);
}

export function endOfYear(d: Date): Date {
  return new Date(d.getFullYear(), 11, 31);
}

export function addYears(d: Date, n: number): Date {
  return new Date(d.getFullYear() + n, 0, 1);
}
