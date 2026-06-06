// Mirrors the backend Pydantic schemas (app/features/tracker/schemas.py).

export type CategoryType =
  | "duration"
  | "match"
  | "rating"
  | "checklist"
  | "note";
export type ColorGroup = "green" | "yellow" | "none";
export type Discipline = "singles" | "doubles";

export interface Category {
  id: number;
  key: string;
  label: string;
  type: CategoryType;
  color_group: ColorGroup;
  sort_order: number;
}

export interface Activity {
  id: number;
  date: string; // YYYY-MM-DD
  category_id: number;
  duration_minutes: number;
  note: string | null;
  is_package_start: boolean; // first session of a coaching package
}

export interface Match {
  id: number;
  date: string;
  category_id: number;
  discipline: Discipline;
  best_of: number; // 3 | 5 | 7
  my_sets: number;
  opp_sets: number;
  event_id: number | null;
  event_name: string | null;
  is_nonplaying: boolean;
  nonplaying_label: string | null; // "Travel" | "Rest"
  note: string | null;
  order_index: number;
}

export interface CellData {
  display: string;
  color: string | null;
}

export interface WeekResponse {
  start: string;
  days: string[]; // 7 ISO dates, Mon..Sun
  categories: Category[];
  activities: Activity[];
  matches: Match[];
  cells: Record<string, CellData>; // key = `${category_id}|${isoDate}`
  physical_checks: Record<string, string[]>; // isoDate -> ticked item keys
  day_notes: Record<string, string>; // isoDate -> note text
}

export interface PhysicalItem {
  key: string;
  label: string;
}

// ---- stats / analysis ----
export interface MatchStats {
  total: number;
  wins: number;
  losses: number;
  ties: number;
  sets_won: number;
  sets_lost: number;
  win_rate: number | null; // 0..1
}

export interface CategoryMinutes {
  key: string;
  label: string;
  minutes: number;
}

export interface BreakdownBucket {
  key: string;
  label: string;
  date_from: string;
  date_to: string;
  minutes: number;
  days_trained: number;
  days_physical: number;
  matches: number;
  wins: number;
  losses: number;
  win_rate: number | null;
}

export interface BreakdownResponse {
  unit: "month" | "week" | "day";
  buckets: BreakdownBucket[];
}

export interface StatsResponse {
  date_from: string;
  date_to: string;
  num_days: number;
  days_trained: number;
  days_physical: number;
  minutes_total: number;
  minutes_by_category: CategoryMinutes[];
  overall: MatchStats;
  singles: MatchStats;
  doubles: MatchStats;
}

// ---- request payloads ----
export interface ActivityIn {
  date: string;
  category_id: number;
  duration_minutes: number;
  note?: string | null;
  is_package_start?: boolean;
}

// ---- coach packages (10-session blocks) ----
export type CoachPackageStatus = "ok" | "low" | "done" | "over";

export interface CoachPackage {
  number: number;
  start_date: string;
  end_date: string;
  used: number;
  size: number;
  remaining: number;
  over: number;
  is_current: boolean;
  status: CoachPackageStatus;
}

export interface CoachPackagesResponse {
  size: number;
  packages: CoachPackage[];
}

export interface MatchIn {
  date: string;
  category_id: number;
  discipline?: Discipline;
  best_of?: number;
  my_sets?: number;
  opp_sets?: number;
  event_name?: string | null;
  is_nonplaying?: boolean;
  nonplaying_label?: string | null;
  note?: string | null;
  order_index?: number;
}

export interface EventOut {
  id: number;
  name: string;
}

export const cellKey = (categoryId: number, isoDate: string) =>
  `${categoryId}|${isoDate}`;
