import { api } from "../../shared/api/client";
import type {
  CategoryFilter,
  DisciplineFilter,
  MatchStatsResponse,
  RatingBreakdown,
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
};
