// Runtime app config (2026-09-25): fetched once at boot from GET /api/config.
// Local machine → { share_mode: false } and nothing changes. On the shared
// read-only host (SHARE_MODE=1) the shell hides the non-shared tabs, shows the
// "Read-only view" banner and the API client refuses writes before they even
// leave the browser. An optional access code (SHARE_KEY on the server) is
// asked for once and remembered in localStorage.

export interface AppConfig {
  share_mode: boolean;
  key_required: boolean;
  /** ISO minute timestamp written by sync.bat; null when unknown. */
  last_sync: string | null;
}

export const LOCAL_CONFIG: AppConfig = {
  share_mode: false,
  key_required: false,
  last_sync: null,
};

const KEY_STORAGE = "road-to-e.share-key";
export const KEY_HEADER = "X-Share-Key";

// Module-level flags read by the API client (it is not a React component).
let shareMode = false;
let shareKey: string | null = null;
try {
  shareKey = localStorage.getItem(KEY_STORAGE);
} catch {
  shareKey = null;
}

export const isShareMode = () => shareMode;
export const getShareKey = () => shareKey;

export function setShareKey(key: string | null) {
  shareKey = key && key.trim() ? key.trim() : null;
  try {
    if (shareKey) localStorage.setItem(KEY_STORAGE, shareKey);
    else localStorage.removeItem(KEY_STORAGE);
  } catch {
    /* private window etc. — the key just won't be remembered */
  }
}

/** Fetch the config. An old backend (no endpoint) or a network hiccup
 *  falls back to local mode so the app never gets stuck on a blank page. */
export async function loadConfig(): Promise<AppConfig> {
  try {
    const res = await fetch("/api/config");
    if (!res.ok) return LOCAL_CONFIG;
    const cfg = (await res.json()) as AppConfig;
    shareMode = Boolean(cfg.share_mode);
    return cfg;
  } catch {
    return LOCAL_CONFIG;
  }
}

/** Probe whether the remembered/entered code opens the API. */
export async function checkShareKey(key: string): Promise<boolean> {
  try {
    const res = await fetch("/api/tracker/last-date", {
      headers: { [KEY_HEADER]: key },
    });
    return res.status !== 401;
  } catch {
    return false;
  }
}

/** Tab ids visible on the shared host (everything else needs local AI or is
 *  the player's own tooling). Order follows the registry. */
export const SHARED_TAB_IDS = new Set(["daily-tracker", "match-stats", "journal"]);
