import { api } from "../../shared/api/client";
import type {
  Levels,
  Pain,
  Program,
  Report,
  Rpe,
  TrainingSession,
} from "./types";

export const trainingApi = {
  getToday: () => api.get<TrainingSession>("/training/today"),

  getProgram: (level?: string) =>
    api.get<Program>(`/training/program${level ? `?level=${level}` : ""}`),

  getLevels: () => api.get<Levels>("/training/levels"),

  getReport: () => api.get<Report>("/training/report"),

  getSession: (level: string, dayIndex: number) =>
    api.get<TrainingSession>(`/training/session/${level}/${dayIndex}`),

  getSessionByDate: (dateIso: string) =>
    api.get<TrainingSession>(`/training/session-by-date?date=${dateIso}`),

  tickItem: (level: string, dayIndex: number, itemId: number, done: boolean) =>
    api.post<TrainingSession>(
      `/training/session/${level}/${dayIndex}/item/${itemId}`,
      { done }
    ),

  complete: (
    level: string,
    dayIndex: number,
    opts?: { note?: string | null; pain?: Pain | null; rpe?: Rpe | null }
  ) =>
    api.post<TrainingSession>(
      `/training/session/${level}/${dayIndex}/complete`,
      {
        note: opts?.note ?? null,
        pain: opts?.pain ?? null,
        rpe: opts?.rpe ?? null,
      }
    ),

  substitute: (level: string, dayIndex: number, itemId: number, exerciseKey: string) =>
    api.post<TrainingSession>(
      `/training/session/${level}/${dayIndex}/item/${itemId}/substitute`,
      { exercise_key: exerciseKey }
    ),

  skip: (level: string, dayIndex: number, itemId: number, skipped: boolean) =>
    api.post<TrainingSession>(
      `/training/session/${level}/${dayIndex}/item/${itemId}/skip`,
      { skipped }
    ),
};
