import { api } from "../../shared/api/client";
import type { Assessment } from "./types";

export const headCoachApi = {
  getAssessment: () => api.get<Assessment>("/head-coach/assessment"),
  generate: () => api.post<Assessment>("/head-coach/generate", {}),
};
