// Diacritic-insensitive search key: "tuan" finds "Tuấn", "pham" finds
// "Phạm". KEEP IN SYNC with the backend's tracker/service._fold (it folds
// the picker search server-side; this folds client-side filters like the
// Database tab's). đ carries no combining mark, so NFD alone won't strip it.
export function fold(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/đ/g, "d");
}
