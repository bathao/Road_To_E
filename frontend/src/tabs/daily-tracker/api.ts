import { api, apiUrl } from "../../shared/api/client";
import type {
  ActivityIn,
  Activity,
  EventOut,
  Match,
  MatchIn,
  PhysicalItem,
  RatingIn,
  DayRating,
  StatsResponse,
  WeekResponse,
} from "./types";

export const trackerApi = {
  getWeek: (startIso: string) =>
    api.get<WeekResponse>(`/tracker/weeks?start=${startIso}`),

  upsertActivity: (payload: ActivityIn) =>
    api.put<Activity | null>("/tracker/activities", payload),

  createMatch: (payload: MatchIn) =>
    api.post<Match>("/tracker/matches", payload),

  updateMatch: (id: number, payload: MatchIn) =>
    api.put<Match>(`/tracker/matches/${id}`, payload),

  deleteMatch: (id: number) => api.del<void>(`/tracker/matches/${id}`),

  upsertRating: (payload: RatingIn) =>
    api.put<DayRating | null>("/tracker/ratings", payload),

  deleteRating: (dateIso: string) =>
    api.del<void>(`/tracker/ratings?date=${dateIso}`),

  searchEvents: (q: string) =>
    api.get<EventOut[]>(`/tracker/events?q=${encodeURIComponent(q)}`),

  getPhysicalItems: () => api.get<PhysicalItem[]>("/tracker/physical-items"),

  setPhysicalChecks: (date: string, items: string[]) =>
    api.put<{ date: string; items: string[] }>("/tracker/physical-checks", {
      date,
      items,
    }),

  getStats: (fromIso: string, toIso: string) =>
    api.get<StatsResponse>(`/tracker/stats?from=${fromIso}&to=${toIso}`),

  exportUrl: (fromIso: string, toIso: string, format: "xlsx" | "csv") =>
    apiUrl(`/tracker/export?from=${fromIso}&to=${toIso}&format=${format}`),
};
