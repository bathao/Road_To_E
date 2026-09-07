import { api, apiUrl } from "../../shared/api/client";
import type {
  ActivityIn,
  Activity,
  BreakdownResponse,
  Category,
  Coach,
  CoachPackagesResponse,
  EventOut,
  Match,
  MatchIn,
  PhysicalItem,
  JournalDay,
  JournalDays,
  JournalMatch,
  Player,
  PlayerIn,
  RatingBreakdown,
  SessionNote,
  SessionNoteIn,
  SessionNoteTag,
  SessionNoteUpdate,
  StatsResponse,
  TaskIn,
  TasksOut,
  TaskUpdate,
  TournamentIn,
  TournamentsResponse,
  WeekResponse,
} from "./types";

export const trackerApi = {
  getWeek: (startIso: string, endIso?: string) =>
    api.get<WeekResponse>(
      `/tracker/weeks?start=${startIso}` + (endIso ? `&end=${endIso}` : "")
    ),

  getLastDate: () => api.get<{ date: string | null }>("/tracker/last-date"),

  getCoachPackages: () =>
    api.get<CoachPackagesResponse>("/tracker/coach-packages"),

  // One-click card action: flag the over-run block's 11th session as the
  // next package's start (equivalent to ticking ★ on that day by hand).
  startNextCoachPackage: () =>
    api.post<CoachPackagesResponse>("/tracker/coach-packages/start-next", {}),

  coachPackageStartAllowed: (dateIso: string) =>
    api.get<{ allowed: boolean }>(
      `/tracker/coach-package-start-allowed?date=${dateIso}`
    ),

  // Coach roster for the session editor's picker (oldest first).
  getCoaches: () => api.get<Coach[]>("/tracker/coaches"),

  createCoach: (name: string, countsPackage: boolean) =>
    api.post<Coach>("/tracker/coaches", {
      name,
      counts_package: countsPackage,
    }),

  upsertActivity: (payload: ActivityIn) =>
    api.put<Activity | null>("/tracker/activities", payload),

  createMatch: (payload: MatchIn) =>
    api.post<Match>("/tracker/matches", payload),

  updateMatch: (id: number, payload: MatchIn) =>
    api.put<Match>(`/tracker/matches/${id}`, payload),

  deleteMatch: (id: number) => api.del<void>(`/tracker/matches/${id}`),

  searchEvents: (q: string) =>
    api.get<EventOut[]>(`/tracker/events?q=${encodeURIComponent(q)}`),

  searchPlayers: (q: string) =>
    api.get<Player[]>(`/tracker/players?q=${encodeURIComponent(q)}`),

  createPlayer: (payload: PlayerIn) =>
    api.post<Player>("/tracker/players", payload),

  // Most recent singles handicap vs an opponent (editor pre-fill).
  lastHandicap: (playerId: number) =>
    api.get<{ found: boolean; handicap: number; handicap_pattern: string | null }>(
      `/tracker/players/${playerId}/last-handicap`
    ),

  updatePlayer: (id: number, payload: PlayerIn) =>
    api.put<Player>(`/tracker/players/${id}`, payload),

  getPhysicalItems: () => api.get<PhysicalItem[]>("/tracker/physical-items"),

  setPhysicalChecks: (date: string, items: string[]) =>
    api.put<{ date: string; items: string[] }>("/tracker/physical-checks", {
      date,
      items,
    }),

  setDayNote: (date: string, text: string) =>
    api.put<{ date: string; text: string }>("/tracker/day-notes", {
      date,
      text,
    }),

  // Journal (session notes: coach items on coach days + lessons any day).
  getJournalDays: (limit = 30, before?: string) =>
    api.get<JournalDays>(
      `/tracker/journal/days?limit=${limit}${before ? `&before=${before}` : ""}`
    ),

  getJournalDay: (dateIso: string) =>
    api.get<JournalDay>(`/tracker/journal/day/${dateIso}`),

  // Per-match journal note → tracker_match.note (blank clears).
  setMatchNote: (matchId: number, note: string) =>
    api.patch<JournalMatch>(`/tracker/matches/${matchId}/note`, { note }),

  getSessionNoteTags: () =>
    api.get<SessionNoteTag[]>("/tracker/session-note-tags"),

  // Tracking board (Journal tab). Every mutation returns the fresh list.
  getTasks: () => api.get<TasksOut>("/tracker/tasks"),

  createTask: (payload: TaskIn) => api.post<TasksOut>("/tracker/tasks", payload),

  updateTask: (id: number, payload: TaskUpdate) =>
    api.patch<TasksOut>(`/tracker/tasks/${id}`, payload),

  deleteTask: (id: number) => api.del<TasksOut>(`/tracker/tasks/${id}`),

  // Tick / un-tick one day of a daily task.
  checkTask: (id: number, dateIso: string, checked: boolean) =>
    api.post<TasksOut>(`/tracker/tasks/${id}/check`, {
      date: dateIso,
      checked,
    }),

  createSessionNote: (payload: SessionNoteIn) =>
    api.post<SessionNote>("/tracker/session-notes", payload),

  updateSessionNote: (id: number, payload: SessionNoteUpdate) =>
    api.patch<SessionNote>(`/tracker/session-notes/${id}`, payload),

  deleteSessionNote: (id: number) =>
    api.del<void>(`/tracker/session-notes/${id}`),

  getCategories: () => api.get<Category[]>("/tracker/categories"),

  getStats: (fromIso: string, toIso: string) =>
    api.get<StatsResponse>(`/tracker/stats?from=${fromIso}&to=${toIso}`),

  getBreakdown: (fromIso: string, toIso: string, unit: "month" | "week" | "day") =>
    api.get<BreakdownResponse>(
      `/tracker/breakdown?from=${fromIso}&to=${toIso}&unit=${unit}`
    ),

  // ELO over time (global — the rating has no discipline/category filter).
  ratingBreakdown: (fromIso: string, toIso: string, unit: "month" | "week" | "day") =>
    api.get<RatingBreakdown>(
      `/tracker/my-rating/breakdown?from=${fromIso}&to=${toIso}&unit=${unit}`
    ),

  exportUrl: (fromIso: string, toIso: string, format: "xlsx" | "csv") =>
    apiUrl(`/tracker/export?from=${fromIso}&to=${toIso}&format=${format}`),
};

// Tournaments: scheduling commitments shown in the Daily Tracker (strip on
// top + section at the bottom). Every mutation returns the fresh full list.
export const tournamentApi = {
  list: () => api.get<TournamentsResponse>("/tournaments"),
  create: (payload: TournamentIn) =>
    api.post<TournamentsResponse>("/tournaments", payload),
  update: (id: number, payload: TournamentIn) =>
    api.put<TournamentsResponse>(`/tournaments/${id}`, payload),
  remove: (id: number) => api.del<TournamentsResponse>(`/tournaments/${id}`),
  // Knocked-out toggle for one entry (false = un-mark a mis-click).
  setEliminated: (entryId: number, eliminated: boolean) =>
    api.patch<TournamentsResponse>(`/tournaments/entries/${entryId}`, {
      eliminated,
    }),
};
