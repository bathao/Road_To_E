import { api } from "../../shared/api/client";
import type {
  AnalysisReport,
  AnalysisReportDetail,
  FindingDecision,
  ModelHealth,
  Profile,
  ProfileIn,
  Report,
  Skill,
  SkillIn,
  Trait,
  TraitIn,
} from "./types";

export const videoApi = {
  health: () => api.get<ModelHealth>("/video/health/model"),

  // ---- profile ----
  getProfile: () => api.get<Profile>("/video/profile"),
  updateProfile: (payload: ProfileIn) => api.put<Profile>("/video/profile", payload),
  regenerateSummary: () => api.post<Profile>("/video/profile/regenerate-summary", {}),

  // ---- traits / findings ----
  listTraits: (status?: string) =>
    api.get<Trait[]>(`/video/traits${status ? `?status=${status}` : ""}`),
  createTrait: (payload: TraitIn) => api.post<Trait>("/video/traits", payload),
  updateTrait: (id: number, payload: TraitIn) =>
    api.put<Trait>(`/video/traits/${id}`, payload),
  deleteTrait: (id: number) => api.del<void>(`/video/traits/${id}`),

  // ---- skill ledger + player report ----
  listSkills: () => api.get<Skill[]>("/video/skills"),
  updateSkill: (setting: string, aspect: string, payload: SkillIn) =>
    api.put<Skill>(`/video/skills/${setting}/${aspect}`, payload),
  regenerateSkills: () => api.post<Skill[]>("/video/skills/regenerate", {}),
  getReport: () => api.get<Report>("/video/report"),

  // ---- analysis reports (pasted text, date-stamped) ----
  listReports: () => api.get<AnalysisReport[]>("/video/reports"),
  getAnalysisReport: (id: number) =>
    api.get<AnalysisReportDetail>(`/video/reports/${id}`),
  createReport: (payload: {
    source_text: string;
    analysis_date?: string | null; // ISO date; defaults today, backdatable, not future
    setting?: string; // practice | match
    title?: string;
    context?: string;
  }) => api.post<AnalysisReport>("/video/reports", payload),
  reviewReport: (id: number, decisions: FindingDecision[]) =>
    api.post<AnalysisReportDetail>(`/video/reports/${id}/review`, { decisions }),
  deleteReport: (id: number) => api.del<void>(`/video/reports/${id}`),
};
