// BBTV Open points → rank mapping (agreed 2026-07-25):
//   G 800–1000 · F ≤1200 · E ≤1400 · D ≤1600 · C ≤1800 · B ≤2000 · A ≤2200.
// Below 800 renders as "H" (under the table's floor).

export function rankOf(points: number | null | undefined): string | null {
  if (points == null) return null;
  if (points < 800) return "H";
  if (points <= 1000) return "G";
  if (points <= 1200) return "F";
  if (points <= 1400) return "E";
  if (points <= 1600) return "D";
  if (points <= 1800) return "C";
  if (points <= 2000) return "B";
  return "A";
}

/** "950 (G)" — or "—" when not rated yet. */
export function pointsLabel(points: number | null | undefined): string {
  if (points == null) return "—";
  return `${points} (${rankOf(points)})`;
}
