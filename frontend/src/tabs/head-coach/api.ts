import { api } from "../../shared/api/client";
import type {
  Assessment,
  ChatHistory,
  DebugOut,
  DirectiveProgressOut,
  GenerateStatus,
  NotesOut,
  Recap,
  RecapPeriod,
  RecapsOut,
} from "./types";

export const headCoachApi = {
  getAssessment: () => api.get<Assessment>("/head-coach/assessment"),
  // Returns immediately with status="generating"; poll getStatus() until it
  // leaves "generating", then refetch the assessment.
  generate: () => api.post<Assessment>("/head-coach/generate", {}),
  getStatus: () => api.get<GenerateStatus>("/head-coach/status"),
  // This week's database actuals vs each trackable directive's weekly target.
  getDirectiveProgress: () =>
    api.get<DirectiveProgressOut>("/head-coach/directive-progress"),
  // Chat with the coach: send returns immediately with a pending coach row;
  // poll getChat() until `pending` is false.
  getChat: () => api.get<ChatHistory>("/head-coach/chat"),
  sendChat: (text: string) => api.post<ChatHistory>("/head-coach/chat", { text }),
  // The coach's notebook (auto-written from chat + player-added).
  getNotes: () => api.get<NotesOut>("/head-coach/notes"),
  addNote: (text: string) => api.post<NotesOut>("/head-coach/notes", { text }),
  deleteNote: (id: number) => api.del<NotesOut>(`/head-coach/notes/${id}`),
  // Recaps: GET is read-only (newest generated one); generateRecap starts a
  // review of the window ending today (week = last 7 days, month = last 30)
  // — poll getRecaps until latest.status leaves "generating".
  getRecaps: (period: RecapPeriod) =>
    api.get<RecapsOut>(`/head-coach/recaps?period=${period}`),
  generateRecap: (period_type: RecapPeriod) =>
    api.post<Recap>("/head-coach/recaps/generate", { period_type }),
  // Dev panel: recent backend log lines + Ollama VRAM occupancy.
  getDebug: () => api.get<DebugOut>("/head-coach/debug"),
};
