import { api } from "../../shared/api/client";
import type { Assessment, GenerateStatus } from "./types";

export const headCoachApi = {
  getAssessment: () => api.get<Assessment>("/head-coach/assessment"),
  // Returns immediately with status="generating"; poll getStatus() until it
  // leaves "generating", then refetch the assessment.
  generate: () => api.post<Assessment>("/head-coach/generate", {}),
  getStatus: () => api.get<GenerateStatus>("/head-coach/status"),
};
