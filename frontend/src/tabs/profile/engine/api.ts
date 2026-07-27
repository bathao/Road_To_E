// API for the player profile / skill ledger / manual findings, used by the
// Profile tab. (The retired paste-analysis /video/reports endpoints were
// deleted 2026-07-27; /api/video stays as the historical prefix.)
import { api } from "../../../shared/api/client";
import type {
  Profile,
  ProfileIn,
  Report,
  Skill,
  SkillIn,
  Trait,
  TraitIn,
} from "./types";

export const videoApi = {
  // ---- profile ----
  getProfile: () => api.get<Profile>("/video/profile"),
  updateProfile: (payload: ProfileIn) => api.put<Profile>("/video/profile", payload),
  regenerateSummary: () => api.post<Profile>("/video/profile/regenerate-summary", {}),

  // ---- traits / findings ----
  listTraits: (status?: string) =>
    api.get<Trait[]>(`/video/traits${status ? `?status=${status}` : ""}`),
  createTrait: (payload: TraitIn) => api.post<Trait>("/video/traits", payload),
  deleteTrait: (id: number) => api.del<void>(`/video/traits/${id}`),

  // ---- skill ledger + player report ----
  listSkills: () => api.get<Skill[]>("/video/skills"),
  updateSkill: (setting: string, aspect: string, payload: SkillIn) =>
    api.put<Skill>(`/video/skills/${setting}/${aspect}`, payload),
  regenerateSkills: () => api.post<Skill[]>("/video/skills/regenerate", {}),
  getReport: () => api.get<Report>("/video/report"),
};
