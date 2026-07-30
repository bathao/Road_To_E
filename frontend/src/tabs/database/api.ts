import { api } from "../../shared/api/client";
import type { Match, Player, PlayerIn } from "../daily-tracker/types";
import type { PlayersDbResponse } from "./types";

// My-rating calls moved to profileApi (the card lives on the Profile tab now).
export const databaseApi = {
  list: () => api.get<PlayersDbResponse>("/tracker/players-db"),
  // Per-player drill-down: every match involving them, any slot, newest first.
  playerMatches: (id: number) =>
    api.get<Match[]>(`/tracker/players/${id}/matches`),
  // Backend is get-or-create by name, so re-adding an existing player is a
  // harmless no-op that returns the existing row.
  createPlayer: (payload: PlayerIn) =>
    api.post<Player>("/tracker/players", payload),
  updatePlayer: (id: number, payload: PlayerIn) =>
    api.put(`/tracker/players/${id}`, payload),
};
