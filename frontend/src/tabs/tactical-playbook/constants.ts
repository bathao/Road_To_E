// Static display helpers for the Tactical Playbook tab. The authoritative
// phase list + suggested chips come from the backend /meta endpoint; this file
// only adds per-phase icons (kept on the frontend to stay dependency-free).
import type { PhaseKey } from "./types";

export const PHASE_ICON: Record<PhaseKey, string> = {
  serve: "🏓",
  receive: "🛡️",
  third_ball: "⚡",
  rally: "🔁",
  general: "🧠",
};
