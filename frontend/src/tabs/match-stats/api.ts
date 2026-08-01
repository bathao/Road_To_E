import { api } from "../../shared/api/client";
import type {
  CategoryFilter,
  DisciplineFilter,
  MatchStatsResponse,
  MyRating,
  RatingBreakdown,
  TournamentRecordResponse,
  TrackerStats,
} from "./types";

export const matchStatsApi = {
  get: (
    fromIso: string,
    toIso: string,
    discipline: DisciplineFilter,
    category: CategoryFilter,
    unit: "month" | "week" | "day"
  ) =>
    api.get<MatchStatsResponse>(
      `/tracker/match-stats?from=${fromIso}&to=${toIso}` +
        `&discipline=${discipline}&category=${category}&unit=${unit}`
    ),

  // ELO over time — GLOBAL (the rating ignores the discipline/category filters).
  ratingBreakdown: (fromIso: string, toIso: string, unit: "month" | "week" | "day") =>
    api.get<RatingBreakdown>(
      `/tracker/my-rating/breakdown?from=${fromIso}&to=${toIso}&unit=${unit}`
    ),

  // ---- the Profile pieces merged into this tab (2026-07-30) ----
  // Read-only: the anchor is fixed (user decision 2026-07-30) — the rating
  // only moves through matches. PUT /tracker/my-rating still exists
  // server-side for a deliberate manual re-anchor.
  getMyRating: () => api.get<MyRating>("/tracker/my-rating"),
  lastDate: () => api.get<{ date: string | null }>("/tracker/last-date"),
  // Same endpoint as the Daily Tracker's aggregates (training discipline card).
  trainingStats: (fromIso: string, toIso: string) =>
    api.get<TrackerStats>(`/tracker/stats?from=${fromIso}&to=${toIso}`),
  // Past-tournament history (rangeless) — derived from the linked matches.
  tournamentRecord: () =>
    api.get<TournamentRecordResponse>("/tournaments/record"),
};
