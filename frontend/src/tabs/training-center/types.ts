// Mirrors backend app/features/training/schemas.py

export type DayType = "legs" | "core" | "balance";
export type ExerciseKind = "reps" | "timed";
export type SessionStatus = "unlocked" | "done";
export type TileStatus = "done" | "unlocked" | "locked";

export interface ExerciseTarget {
  sets?: number;
  reps?: number;
  sec?: number;
}

export interface SessionItem {
  id: number;
  exercise_key: string;
  name_vi: string;
  muscle: string;
  tt_benefit: string;
  kind: ExerciseKind;
  target: ExerciseTarget;
  per_side: boolean;
  gif: string;
  form_cue: string;
  done: boolean;
  is_prescribed: boolean;
  rx_reason: string | null;
}

export interface TrainingSession {
  id: number;
  level: string;
  level_vi: string;
  day_index: number;
  day_type: DayType;
  focus_vi: string;
  est_minutes: number;
  status: SessionStatus;
  done_count: number;
  total: number;
  progress_pct: number;
  done_on: string | null;
  note: string | null;
  items: SessionItem[];
}

export interface DayTile {
  day_index: number;
  day_type: DayType;
  focus_vi: string;
  status: TileStatus;
  thumb: string;
}

export interface Program {
  level: string;
  level_vi: string;
  goal_vi: string;
  safety_note: string;
  cycle: number; // 1-based maintenance cycle ("Vòng N"); 1 for finite levels
  total_sessions: number;
  completed: number;
  progress_pct: number;
  tiles: DayTile[];
}

export interface LevelInfo {
  key: string;
  label_vi: string;
  goal_vi: string;
  unlocked: boolean;
  completed: number;
  total: number;
}

export interface Levels {
  current_level: string;
  levels: LevelInfo[];
}

export interface MuscleVolume {
  muscle: string;
  times: number;
}

export interface RecentSession {
  done_on: string;
  level: string;
  day_index: number;
  focus_vi: string;
  done_count: number;
  total: number;
}

export interface Report {
  current_level: string;
  current_level_vi: string;
  cutover_date: string | null;
  total_sessions_done: number;
  sessions_last_7d: number;
  sessions_last_30d: number;
  last_session_date: string | null;
  days_since_last: number | null;
  day_type_counts: Record<string, number>;
  muscle_volume: MuscleVolume[];
  levels: LevelInfo[];
  recent: RecentSession[];
  summary_vi: string;
}
