import { api } from "../../shared/api/client";
import type { LibraryItem, PlaybookMeta, Tactic, TacticIn } from "./types";

export const playbookApi = {
  getMeta: () => api.get<PlaybookMeta>("/playbook/meta"),

  getLibrary: () => api.get<LibraryItem[]>("/playbook/library"),

  getTactics: () => api.get<Tactic[]>("/playbook/tactics"),

  createTactic: (payload: TacticIn) =>
    api.post<Tactic>("/playbook/tactics", payload),

  updateTactic: (id: number, payload: TacticIn) =>
    api.put<Tactic>(`/playbook/tactics/${id}`, payload),

  deleteTactic: (id: number) => api.del<void>(`/playbook/tactics/${id}`),
};
