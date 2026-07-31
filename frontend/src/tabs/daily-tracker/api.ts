import { api, apiUrl } from "../../shared/api/client";
import type {
  ActivityIn,
  Activity,
  BreakdownResponse,
  Category,
  CoachPackagesResponse,
  EventOut,
  Match,
  MatchIn,
  PhysicalItem,
  Player,
  PlayerIn,
  RatingBreakdown,
  SessionNote,
  SessionNoteIn,
  SessionNoteTag,
  SessionNoteUpdate,
  StatsResponse,
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

  upsertActivity: (payload: ActivityIn) =>
    api.put<Activity | null>("/tracker/activities", payload),

  createMatch: (payload: MatchIn) =>
    api.post<Match>("/tracker/matches", payload),

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

  // Coach & Recap row (structured advice/recap items on coach days).
  getSessionNoteTags: () =>
    api.get<SessionNoteTag[]>("/tracker/session-note-tags"),

  // All advice not yet marked done, oldest first (the standing checklist).
  getActiveAdvice: () =>
    api.get<SessionNote[]>("/tracker/session-notes/active"),

  createSessionNote: (payload: SessionNoteIn) =>
    api.post<SessionNote>("/tracker/session-notes", payload),

  updateSessionNote: (id: number, payload: SessionNoteUpdate) =>
    api.patch<SessionNote>(`/tracker/session-notes/${id}`, payload),

  deleteSessionNote: (id: number) =>
    api.del<void>(`/tracker/session-notes/${id}`),

  getCategories: () => api.get<Category[]>("/tracker/categories"),

  getStats: (fromIso: string, toIso: string) =>
    api.get<StatsResponse>(`/tracker/stats?from=${fromIso}&to=${toIso}`),

  // Drill-down behind one stat card — same filter as /stats, newest first.
  statsMatches: (fromIso: string, toIso: string, bucket: string) =>
    api.get<Match[]>(
      `/tracker/stats/matches?from=${fromIso}&to=${toIso}&bucket=${bucket}`
    ),

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
};
