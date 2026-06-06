import { api } from "../../shared/api/client";
import type {
  CategoryFilter,
  DisciplineFilter,
  MatchStatsResponse,
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
};
