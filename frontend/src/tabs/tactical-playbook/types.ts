// Types for the Tactical Playbook tab. Mirror the backend playbook schemas.

export type PhaseKey = "serve" | "receive" | "third_ball" | "rally" | "general";

// A tactic the user can apply (their own playbook entry).
export interface Tactic {
  id: number;
  phase: PhaseKey;
  title: string;
  when_to_use: string | null;
  how_to: string | null;
  follow_up: string | null;
  risk: string | null;
  opponent_styles: string[];
  tags: string[];
  confidence: number; // 0-5 stars
  is_favorite: boolean;
  source_key: string | null; // Library item it was copied from (if any)
  sort_order: number;
}

// Payload for create/update.
export interface TacticIn {
  phase: PhaseKey;
  title: string;
  when_to_use?: string | null;
  how_to?: string | null;
  follow_up?: string | null;
  risk?: string | null;
  opponent_styles?: string[];
  tags?: string[];
  confidence?: number;
  is_favorite?: boolean;
  source_key?: string | null;
}

// A built-in Library item (general tactic, read-only reference).
export interface LibraryItem {
  key: string;
  phase: PhaseKey;
  title: string;
  when_to_use: string | null;
  how_to: string | null;
  follow_up: string | null;
  risk: string | null;
  opponent_styles: string[];
  tags: string[];
  source: string | null; // coaching source name
  source_url: string | null;
}

export interface PhaseMeta {
  key: PhaseKey;
  label: string;
}

export interface PlaybookMeta {
  phases: PhaseMeta[];
  spin_tags: string[];
  placement_tags: string[];
  opponent_styles: string[];
}
