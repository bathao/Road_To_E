import { api, apiUrl } from "../../shared/api/client";
import type {
  ActivityIn,
  Activity,
  BreakdownResponse,
  EventOut,
  Match,
  MatchIn,
  PhysicalItem,
  StatsResponse,
  WeekResponse,
} from "./types";

export const trackerApi = {
  getWeek: (startIso: string) =>
    api.get<WeekResponse>(`/tracker/weeks?start=${startIso}`),

  getLastDate: () => api.get<{ date: string | null }>("/tracker/last-date"),

  upsertActivity: (payload: ActivityIn) =>
    api.put<Activity | null>("/tracker/activities", payload),

  createMatch: (payload: MatchIn) =>
    api.post<Match>("/tracker/matches", payload),

  updateMatch: (id: number, payload: MatchIn) =>
    api.put<Match>(`/tracker/matches/${id}`, payload),

  deleteMatch: (id: number) => api.del<void>(`/tracker/matches/${id}`),

  searchEvents: (q: string) =>
    api.get<EventOut[]>(`/tracker/events?q=${encodeURIComponent(q)}`),

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

  getStats: (fromIso: string, toIso: string) =>
    api.get<StatsResponse>(`/tracker/stats?from=${fromIso}&to=${toIso}`),

  getBreakdown: (fromIso: string, toIso: string, unit: "month" | "week" | "day") =>
    api.get<BreakdownResponse>(
      `/tracker/breakdown?from=${fromIso}&to=${toIso}&unit=${unit}`
    ),

  exportUrl: (fromIso: string, toIso: string, format: "xlsx" | "csv") =>
    apiUrl(`/tracker/export?from=${fromIso}&to=${toIso}&format=${format}`),
};
