import { api } from "../../shared/api/client";
import type { MatchStatsLite, MyRating, RatingBreakdown, TrackerStats } from "./types";

// The Profile dashboard assembles data from existing endpoints: the tracker
// aggregates, the "as of" date and the user's dynamic ELO (the anchor edit
// lives here too — moved from the Database tab 2026-07-27).
export const profileApi = {
  trainingStats: (fromIso: string, toIso: string) =>
    api.get<TrackerStats>(`/tracker/stats?from=${fromIso}&to=${toIso}`),
  matchStats: (fromIso: string, toIso: string) =>
    api.get<MatchStatsLite>(
      `/tracker/match-stats?from=${fromIso}&to=${toIso}` +
        `&discipline=all&category=all&unit=month`
    ),
  lastDate: () => api.get<{ date: string | null }>("/tracker/last-date"),
  getMyRating: () => api.get<MyRating>("/tracker/my-rating"),
  setMyRating: (points: number) =>
    api.put<MyRating>("/tracker/my-rating", { points }),
  ratingBreakdown: (fromIso: string, toIso: string, unit: "day" | "week" | "month") =>
    api.get<RatingBreakdown>(
      `/tracker/my-rating/breakdown?from=${fromIso}&to=${toIso}&unit=${unit}`
    ),
};
