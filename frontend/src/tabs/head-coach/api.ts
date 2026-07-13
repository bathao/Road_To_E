import { api } from "../../shared/api/client";
import type { Assessment, DirectiveProgressOut, GenerateStatus } from "./types";

export const headCoachApi = {
  getAssessment: () => api.get<Assessment>("/head-coach/assessment"),
  // Returns immediately with status="generating"; poll getStatus() until it
  // leaves "generating", then refetch the assessment.
  generate: () => api.post<Assessment>("/head-coach/generate", {}),
  getStatus: () => api.get<GenerateStatus>("/head-coach/status"),
  // This week's database actuals vs each trackable directive's weekly target.
  getDirectiveProgress: () =>
    api.get<DirectiveProgressOut>("/head-coach/directive-progress"),
};
