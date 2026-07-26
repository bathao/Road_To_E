import { api } from "../../shared/api/client";
import type { PlayerIn } from "../daily-tracker/types";
import type { MyRating, MyRatingHistory, PlayersDbResponse } from "./types";

export const databaseApi = {
  list: () => api.get<PlayersDbResponse>("/tracker/players-db"),
  updatePlayer: (id: number, payload: PlayerIn) =>
    api.put(`/tracker/players/${id}`, payload),
  getMyRating: () => api.get<MyRating>("/tracker/my-rating"),
  setMyRating: (points: number) =>
    api.put<MyRating>("/tracker/my-rating", { points }),
  ratingHistory: () => api.get<MyRatingHistory>("/tracker/my-rating/history"),
};
