// Small formatting helpers shared across tabs.

/** A 0..1 rate as a rounded percent, or "—" when there is no rate. */
export function pct(rate: number | null): string {
  return rate === null ? "—" : `${Math.round(rate * 100)}%`;
}

/** Minutes as "1h 30m" / "45m" / "2h"; "0m" for 0. */
export function fmtMinutes(min: number): string {
  if (!min) return "0m";
  const h = Math.floor(min / 60);
  const m = min % 60;
  return [h ? `${h}h` : "", m ? `${m}m` : ""].filter(Boolean).join(" ");
}
