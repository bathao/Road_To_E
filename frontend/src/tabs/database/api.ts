import { api } from "../../shared/api/client";
import type { PlayerIn } from "../daily-tracker/types";
import type { PlayersDbResponse } from "./types";

// My-rating calls moved to profileApi (the card lives on the Profile tab now).
export const databaseApi = {
  list: () => api.get<PlayersDbResponse>("/tracker/players-db"),
  updatePlayer: (id: number, payload: PlayerIn) =>
    api.put(`/tracker/players/${id}`, payload),
};
