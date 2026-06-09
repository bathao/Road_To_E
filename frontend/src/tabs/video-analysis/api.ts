import { api, apiUrl } from "../../shared/api/client";
import type {
  Clip,
  ClipDetail,
  ClipType,
  FindingDecision,
  Focus,
  ModelHealth,
  Profile,
  ProfileImage,
  ProfileIn,
  Report,
  Side,
  Skill,
  SkillIn,
  Trait,
  TraitIn,
} from "./types";

export const videoApi = {
  health: () => api.get<ModelHealth>("/video/health/model"),

  // Open a native file dialog on the local machine, returns the chosen path.
  // kind: "video" (default) or "image" (for reference photos).
  browse: (kind: "video" | "image" = "video") =>
    api.post<{ path: string }>(`/video/browse?kind=${kind}`, {}),

  // ---- profile reference images (identity gallery) ----
  listProfileImages: () => api.get<ProfileImage[]>("/video/profile/images"),
  addProfileImage: (local_path: string) =>
    api.post<ProfileImage>("/video/profile/images", { local_path }),
  deleteProfileImage: (id: number) => api.del<void>(`/video/profile/images/${id}`),
  profileImageUrl: (id: number) => apiUrl(`/video/profile/images/${id}/file`),

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

  // ---- skill ledger + report ----
  listSkills: () => api.get<Skill[]>("/video/skills"),
  updateSkill: (aspect: string, payload: SkillIn) =>
    api.put<Skill>(`/video/skills/${aspect}`, payload),
  regenerateSkills: () => api.post<Skill[]>("/video/skills/regenerate", {}),
  getReport: () => api.get<Report>("/video/report"),

  // ---- clips ----
  listClips: () => api.get<Clip[]>("/video/clips"),
  getClip: (id: number) => api.get<ClipDetail>(`/video/clips/${id}`),
  reanalyze: (id: number, model?: string) =>
    api.post<Clip>(`/video/clips/${id}/reanalyze`, model ? { model } : {}),
  identify: (id: number, me_side: Side, me_appearance: string) =>
    api.post<Clip>(`/video/clips/${id}/identify`, { me_side, me_appearance }),
  confirm: (id: number) => api.post<Clip>(`/video/clips/${id}/confirm`, {}),
  stop: (id: number) => api.post<Clip>(`/video/clips/${id}/stop`, {}),
  review: (id: number, decisions: FindingDecision[]) =>
    api.post<ClipDetail>(`/video/clips/${id}/review`, { decisions }),
  deleteClip: (id: number) => api.del<void>(`/video/clips/${id}`),
  videoUrl: (id: number) => apiUrl(`/video/clips/${id}/video`),
  previewUrl: (id: number) => apiUrl(`/video/clips/${id}/preview`),
  evidenceUrl: (id: number, thumb: string) =>
    apiUrl(`/video/clips/${id}/evidence/${thumb}`),
  frameUrl: (id: number) => apiUrl(`/video/clips/${id}/frame`),
  cropReference: (id: number, box: { x: number; y: number; w: number; h: number }) =>
    api.post<ProfileImage>(`/video/clips/${id}/crop-reference`, box),

  // Local-only: the server reads a file already on disk. trim_start/trim_end
  // (mm:ss or seconds) cut a short segment first; only the cut is kept.
  createClip: (form: {
    local_path: string;
    clip_type: ClipType;
    focus?: Focus;
    title: string;
    note?: string;
    model?: string;
    trim_start?: string;
    trim_end?: string;
    me_side?: Side;
    me_appearance?: string;
  }) => api.post<Clip>("/video/clips", form),
};
