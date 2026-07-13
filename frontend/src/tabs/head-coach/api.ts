import { api } from "../../shared/api/client";
import type {
  Assessment,
  ChatHistory,
  DebugOut,
  DirectiveProgressOut,
  GenerateStatus,
  NotesOut,
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
  // Dev panel: recent backend log lines + Ollama VRAM occupancy.
  getDebug: () => api.get<DebugOut>("/head-coach/debug"),
};
