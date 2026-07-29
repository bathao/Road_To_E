// Match disciplines + their display labels, shared by every tab.
// one_v_two = I play ALONE vs two opponents; two_v_one = me + partner vs one.

export type Discipline = "singles" | "doubles" | "one_v_two" | "two_v_one";

/** Seg-button order + full label. */
export const DISCIPLINES: [Discipline, string][] = [
  ["singles", "Singles"],
  ["doubles", "Doubles"],
  ["one_v_two", "1v2"],
  ["two_v_one", "2v1"],
];

/** Full label per discipline ("Singles" …). */
export const DISCIPLINE_LABEL: Record<Discipline, string> = Object.fromEntries(
  DISCIPLINES
) as Record<Discipline, string>;

/** Compact tag ("S" / "D" / "1v2" / "2v1") for list rows and chips. */
export const DISCIPLINE_SHORT: Record<Discipline, string> = {
  singles: "S",
  doubles: "D",
  one_v_two: "1v2",
  two_v_one: "2v1",
};
