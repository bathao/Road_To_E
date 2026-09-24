// Mirrors the backend Pydantic schemas (app/features/tracker/schemas.py).

export type CategoryType =
  | "duration"
  | "match"
  | "rating"
  | "checklist"
  | "note"
  | "computed" // auto-calculated read-only row (Racket Time)
  // Legacy Coach & Recap row type — filtered out of the grid by the backend
  // since 2026-08-20 (the data lives in the Journal tab now).
  | "session_note";
export type ColorGroup = "green" | "yellow" | "none";
// one_v_two = I play ALONE vs two opponents; two_v_one = me + partner vs one.
export type { Discipline } from "../../shared/disciplines";
import type { Discipline } from "../../shared/disciplines";
import type { TournamentRound } from "../../shared/matches";

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
  // Which coach the session was with (train_with_coach rows only; the name
  // is resolved from GET /tracker/coaches). null = legacy/default coach.
  coach_id?: number | null;
}

// A real-life coach (Minh Thới, Phi Vũ, …). counts_package: sessions consume
// the 10-session block; false = paid per session, never on the block.
export interface Coach {
  id: number;
  name: string;
  counts_package: boolean;
}

// Skill level of a player relative to me (canonical definition in shared/).
import type { PlayerLevel } from "../../shared/levels";
export type { PlayerLevel };

export interface Player {
  id: number;
  name: string;
  level: PlayerLevel;
  note?: string | null;
  plays_pips: boolean; // opponent uses pimpled rubber ("đánh gai")
  points?: number | null; // BBTV points (Database tab); null = not rated
}

export interface PlayerIn {
  name: string;
  // Omitted on create = backend derives the legacy label from points;
  // omitted on update = label left untouched.
  level?: PlayerLevel;
  note?: string | null;
  plays_pips?: boolean;
  points?: number | null; // omitted/null on update = leave unchanged
  // What a points change means (default progression): "progression" = real
  // level change, applies to matches entered from now on; "correction" =
  // the old value was a typo — every stored snapshot of this player is
  // re-frozen and ELO history recalculates.
  points_intent?: "progression" | "correction";
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
  // Who played. Singles: opponent_*. Doubles: partner_* + opponent_* + opponent2_*.
  opponent_id: number | null;
  opponent_name: string | null;
  opponent_level: PlayerLevel | null;
  opponent_plays_pips: boolean;
  opponent2_id: number | null;
  opponent2_name: string | null;
  opponent2_level: PlayerLevel | null;
  opponent2_plays_pips: boolean;
  partner_id: number | null;
  partner_name: string | null;
  partner_level: PlayerLevel | null;
  handicap: number; // signed: +N = I give N points, -N = I receive
  // Per-set sequence for non-uniform ratios ("2-0-2"); null = uniform.
  handicap_pattern?: string | null;
  // Tournament link: the registered entry the match belongs to + the round
  // played; null on ordinary matches. (The API also echoes tournament_name;
  // nothing here reads it — the editor labels via tournamentCtx instead.)
  tournament_entry_id?: number | null;
  round?: TournamentRound | null;
  // ELO annotation (week view): ±Δ this match moved MY rating, or why it
  // doesn't count ("counted" | "nonplaying" | "before_anchor" |
  // "no_opponent" | "no_result" | "unrated").
  elo_delta?: number | null;
  elo_status?: string | null;
}

export interface CellData {
  display: string;
  color: string | null;
}

// ---- session notes (Journal tab; formerly the Coach & Recap row) ----
// advice = coach's instruction (done-lifecycle) · drill = one exercise of
// the session (auto-numbered by entry order) · recap = overall summary ·
// lesson = the player's own takeaway of the day (any day, no lifecycle).
export type SessionNoteKind = "advice" | "drill" | "recap" | "lesson";

export interface SessionNote {
  id: number;
  date: string;
  kind: SessionNoteKind;
  tags: string[]; // keys from GET /session-note-tags
  text: string;
  // Advice lifecycle: stays "active" (shown in the editor checklist + fed to
  // the AI coach) until ticked done. Always false for recaps.
  is_done: boolean;
}

export interface SessionNoteIn {
  date: string;
  kind: SessionNoteKind;
  tags: string[];
  text: string;
}

export interface SessionNoteUpdate {
  tags?: string[];
  text?: string;
  is_done?: boolean;
}

export interface SessionNoteTag {
  key: string;
  label: string;
}

// ---- Journal tab (timeline over the session-note store) ----
// One of the day's matches in the journal's Matches area — the note writes
// straight to tracker_match.note (and the Tactics h2h context reads it).
export interface JournalMatch {
  id: number;
  label: string; // e.g. "W 3-2 vs Nguyễn Văn Trung · receive 2"
  note: string;
}

export interface JournalDay {
  date: string;
  coaches: string[]; // Train-with-Coach coach names that day
  has_coach_session: boolean; // gates the composer's coach-reminder block
  items: SessionNote[];
  // Composer day: ALL the day's matches; timeline days: noted matches only.
  matches: JournalMatch[];
}

export interface JournalDays {
  days: JournalDay[]; // newest first, only days WITH entries
  has_more: boolean;
}

export interface WeekResponse {
  start: string;
  days: string[]; // 7 ISO dates, Mon..Sun
  categories: Category[];
  activities: Activity[];
  matches: Match[];
  cells: Record<string, CellData>; // key = `${category_id}|${isoDate}`
  physical_checks: Record<string, string[]>; // isoDate -> ticked item keys (legacy)
  day_notes: Record<string, string>; // isoDate -> note text
  // From this date forward the Physical row mirrors Training Center (read-only
  // in the grid). null = unset (no Training Center activity yet).
  physical_cutover: string | null;
}

export interface PhysicalItem {
  key: string;
  label: string;
}

// ---- Tracking board (Journal tab, 2026-08-24) ----
export type TaskSource = "coach" | "ai" | "self";
export type TaskStatus = "todo" | "doing" | "done";

// Mirrors backend tracker/schemas.py TaskOut.
export interface Task {
  id: number;
  title: string;
  note: string;
  source: TaskSource;
  status: TaskStatus;
  is_daily: boolean;
  created_at: string;
  done_at: string | null;
  // Daily-task extras (0/false/null on one-off tasks):
  checked_today: boolean;
  streak: number; // consecutive practiced days (today, or ending yesterday)
  last_check: string | null;
}

export interface TasksOut {
  tasks: Task[]; // open + done-in-last-7-days; every mutation returns this
}

export interface TaskIn {
  title: string;
  note?: string;
  source?: TaskSource;
  is_daily?: boolean;
}

export interface TaskUpdate {
  title?: string;
  note?: string;
  source?: TaskSource;
  status?: TaskStatus;
  is_daily?: boolean;
}

// ---- Remember board (Journal tab, 2026-09-24) ----
// Mirrors backend tracker/schemas.py MemoOut. A standing reminder — no
// status, no date, no tick; list order is the priority.
export interface Memo {
  id: number;
  text: string;
  sort_order: number;
  created_at: string;
  updated_at: string;
}

export interface MemosOut {
  memos: Memo[]; // priority order; every mutation returns this
}

// ---- stats / analysis ----
import type { CategoryMinutes, MatchStats } from "../../shared/types";

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
  // Racket time = coach + partner training + match play (sets × ~5 min).
  racket_minutes_total: number;
  racket_minutes_training: number;
  racket_minutes_matches: number;
  // Match buckets below are mirrored for completeness but the FE no longer
  // reads them (the Daily Tracker win-rate cards were removed 2026-08-02) —
  // they feed the coach bundle in-process; Profile match stats come from
  // /tracker/match-stats instead.
  overall: MatchStats;
  singles: MatchStats;
  doubles: MatchStats;
  one_v_two: MatchStats; // I play alone vs two opponents
  two_v_one: MatchStats; // me + partner vs one opponent
  vs_pips: MatchStats; // matches vs a pimpled-rubber opponent ("gai")
}

// ---- my ELO over time (GET /tracker/my-rating/breakdown) ----
export interface RatingBucket {
  key: string;
  label: string;
  date_from: string;
  date_to: string;
  delta: number; // net ±Δ of the bucket's counted matches (0 when none)
  counted: number;
  // Rating at the bucket's end (carry-forward on quiet days); null = the
  // bucket ends before the anchor, when no rating existed yet.
  rating_end: number | null;
}

export interface RatingMover {
  // null = a tournament placement bonus row (see bonus_label), not a match.
  match_id: number | null;
  date: string;
  delta: number;
  discipline: Discipline | "team"; // "team" only on bonus rows (team events)
  opponent_name: string | null;
  // Full line-up for team formats; null where the format skips the slot.
  opponent2_name: string | null;
  partner_name: string | null;
  my_sets: number;
  opp_sets: number;
  bonus_label?: string | null; // "Giải X — Champion" on bonus rows
}

// Global — the rating has no discipline/category filter.
export interface RatingBreakdown {
  date_from: string;
  date_to: string;
  unit: "day" | "week" | "month";
  anchor_date: string;
  anchor_points: number; // anchor value — pre-anchor days draw flat at this
  total_delta: number;
  counted: number;
  rating_start: number | null;
  rating_end: number | null;
  buckets: RatingBucket[];
  // Every counted match in the range, biggest |Δ| first (the Match Stats
  // table sorts client-side).
  movers: RatingMover[];
}

// ---- request payloads ----
export interface ActivityIn {
  date: string;
  category_id: number;
  duration_minutes: number;
  note?: string | null;
  is_package_start?: boolean;
  // train_with_coach rows only; omitted = backend keeps the stored coach
  // (or defaults a new row to the package coach).
  coach_id?: number | null;
}

// ---- tournaments (scheduling commitments; match results stay in the grid) ----
export type TournamentDiscipline = "singles" | "doubles" | "team";

// Only the fields the Daily Tracker reads — the API also echoes derived
// result fields (final_placement, bonus_points, data_warning), but those
// are rendered exclusively by the Profile tab's Tournament Record, which
// has its own mirror (tabs/match-stats/types.ts RecordEntryInfo).
export interface TournamentEntry {
  id: number;
  discipline: TournamentDiscipline;
  partner_id?: number | null;
  partner_name?: string | null; // resolved by the backend for display
  teammate_ids?: number[]; // team roster (players from the shared pool)
  teammate_names?: string[]; // resolved, same order as ids
  team_members?: string | null; // optional team name / note
  division?: string | null; // "hạng E", "U40"…
  // Deepest DECIDED round of the linked matches + whether it was won —
  // derived server-side, feeds the MatchEditor's auto-advancing Round
  // default (works across the days of a multi-day event).
  latest_round?: string | null;
  latest_round_won?: boolean | null;
  // Knocked out mid-event (user button): the grid highlight / editor
  // tournament mode skip this entry on the event's remaining days.
  eliminated?: boolean;
}

export interface Tournament {
  id: number;
  name: string;
  location?: string | null;
  start_date: string;
  end_date?: string | null; // null = single-day
  level_limit?: string | null; // allowed ranks, free text ("E F G"…)
  points_limit?: number | null; // points-capped tournaments (≤N points)
  note?: string | null;
  // Ended before today OR results already entered — the strip + section
  // filter played tournaments OUT on this flag (history lives in the
  // Profile tab's Tournament Record).
  played: boolean;
  entries: TournamentEntry[];
}

export interface TournamentEntryIn {
  // Existing entry's id when editing (null/omitted = create new) — the
  // backend reconciles by id so matches linked to the entry stay linked.
  id?: number | null;
  discipline: TournamentDiscipline;
  partner_id?: number | null;
  teammate_ids?: number[];
  team_members?: string | null;
  division?: string | null;
}

export interface TournamentIn {
  name: string;
  location?: string | null;
  start_date: string;
  end_date?: string | null;
  level_limit?: string | null;
  points_limit?: number | null;
  note?: string | null;
  entries: TournamentEntryIn[];
}

export interface TournamentsResponse {
  // Upcoming first (soonest on top), then past (newest first).
  tournaments: Tournament[];
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
  // Pay-per-session coaches' session counts since the current block opened
  // — excluded from the block, surfaced per coach on the card.
  non_package: { coach_name: string; sessions: number }[];
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
  opponent_id?: number | null;
  opponent2_id?: number | null;
  partner_id?: number | null;
  handicap?: number;
  handicap_pattern?: string | null;
  tournament_entry_id?: number | null;
  round?: TournamentRound | null;
}

export interface EventOut {
  id: number;
  name: string;
}

export const cellKey = (categoryId: number, isoDate: string) =>
  `${categoryId}|${isoDate}`;
