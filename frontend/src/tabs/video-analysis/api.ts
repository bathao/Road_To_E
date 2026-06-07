import { api, apiUrl } from "../../shared/api/client";
import type {
  Clip,
  ClipDetail,
  ClipType,
  ModelHealth,
  Profile,
  ProfileImage,
  ProfileIn,
  Side,
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

  // ---- traits ----
  listTraits: () => api.get<Trait[]>("/video/traits"),
  createTrait: (payload: TraitIn) => api.post<Trait>("/video/traits", payload),
  updateTrait: (id: number, payload: TraitIn) =>
    api.put<Trait>(`/video/traits/${id}`, payload),
  deleteTrait: (id: number) => api.del<void>(`/video/traits/${id}`),

  // ---- clips ----
  listClips: () => api.get<Clip[]>("/video/clips"),
  getClip: (id: number) => api.get<ClipDetail>(`/video/clips/${id}`),
  reanalyze: (id: number, model?: string) =>
    api.post<Clip>(`/video/clips/${id}/reanalyze`, model ? { model } : {}),
  identify: (id: number, me_side: Side, me_appearance: string) =>
    api.post<Clip>(`/video/clips/${id}/identify`, { me_side, me_appearance }),
  confirm: (id: number) => api.post<Clip>(`/video/clips/${id}/confirm`, {}),
  deleteClip: (id: number) => api.del<void>(`/video/clips/${id}`),
  videoUrl: (id: number) => apiUrl(`/video/clips/${id}/video`),
  previewUrl: (id: number) => apiUrl(`/video/clips/${id}/preview`),
  frameUrl: (id: number) => apiUrl(`/video/clips/${id}/frame`),
  cropReference: (id: number, box: { x: number; y: number; w: number; h: number }) =>
    api.post<ProfileImage>(`/video/clips/${id}/crop-reference`, box),

  // Local-only: the server reads a file already on disk. trim_start/trim_end
  // (mm:ss or seconds) cut a short segment first; only the cut is kept.
  createClip: (form: {
    local_path: string;
    clip_type: ClipType;
    title: string;
    note?: string;
    model?: string;
    trim_start?: string;
    trim_end?: string;
    me_side?: Side;
    me_appearance?: string;
  }) => api.post<Clip>("/video/clips", form),
};
