import { api } from "../../shared/api/client";
import type { Match } from "../daily-tracker/types";
import type {
  AnswerIn,
  Fact,
  FactKind,
  FactsOut,
  InterviewOut,
  Opponent,
  TacticPlan,
} from "./types";

export const tacticsApi = {
  getOpponents: () => api.get<Opponent[]>("/tactics/opponents"),

  // H2H detail rides the existing per-player endpoint (any slot, newest
  // first, ELO-annotated); the tab filters to opposing-side matches.
  playerMatches: (id: number) =>
    api.get<Match[]>(`/tracker/players/${id}/matches`),

  getFacts: (playerId: number) => api.get<FactsOut>(`/tactics/facts/${playerId}`),

  addFact: (playerId: number | null, kind: FactKind, text: string) =>
    api.post<Fact>("/tactics/facts", { player_id: playerId, kind, text }),

  updateFact: (id: number, text: string) =>
    api.put<Fact>(`/tactics/facts/${id}`, { text }),

  deleteFact: (id: number) => api.del<{ ok: boolean }>(`/tactics/facts/${id}`),

  // Synchronous LLM call — slow-ish; the button shows a spinner meanwhile.
  interview: (playerId: number) =>
    api.post<InterviewOut>("/tactics/interview", { player_id: playerId }),

  saveAnswers: (playerId: number, items: AnswerIn[]) =>
    api.post<FactsOut>("/tactics/interview/answers", {
      player_id: playerId,
      items,
    }),

  getPlan: (playerId: number) => api.get<TacticPlan>(`/tactics/plan/${playerId}`),

  generatePlan: (playerId: number) =>
    api.post<TacticPlan>(`/tactics/plan/${playerId}`, {}),
};
