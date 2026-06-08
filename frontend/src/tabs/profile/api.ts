import { api } from "../../shared/api/client";
import type { MatchStatsLite, TrackerStats } from "./types";

// The Profile dashboard is read-only and assembles data from existing
// endpoints. Skill/report/profile calls reuse `videoApi`; here we add the two
// tracker aggregates plus the "as of" date.
export const profileApi = {
  trainingStats: (fromIso: string, toIso: string) =>
    api.get<TrackerStats>(`/tracker/stats?from=${fromIso}&to=${toIso}`),
  matchStats: (fromIso: string, toIso: string) =>
    api.get<MatchStatsLite>(
      `/tracker/match-stats?from=${fromIso}&to=${toIso}` +
        `&discipline=all&category=all&unit=month`
    ),
  lastDate: () => api.get<{ date: string | null }>("/tracker/last-date"),
};
