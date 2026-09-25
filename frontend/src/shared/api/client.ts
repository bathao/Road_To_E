// Thin fetch wrapper. All API calls go through here so the base URL and
// error handling live in one place.
import { getShareKey, isShareMode, KEY_HEADER } from "../config";

const BASE = "/api";

export const READ_ONLY_MESSAGE =
  "Read-only shared view: changes are disabled.";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  // Shared view with an access code: every call carries it.
  const key = getShareKey();
  if (key) headers[KEY_HEADER] = key;
  const res = await fetch(`${BASE}${path}`, { headers, ...init });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  // 204 No Content has no body.
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// On the shared read-only host a write is refused here, before the request
// leaves the browser: the server would 403 it anyway, but this way the editor
// shows one clear sentence instead of a raw status line.
function mutate<T>(path: string, init: RequestInit): Promise<T> {
  if (isShareMode()) return Promise.reject(new Error(READ_ONLY_MESSAGE));
  return request<T>(path, init);
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    mutate<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    mutate<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    mutate<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T>(path: string) => mutate<T>(path, { method: "DELETE" }),
};

// Build the full URL for direct browser navigation (downloads etc.). A plain
// navigation cannot send the X-Share-Key header, so the code rides as ?key=.
export const apiUrl = (path: string) => {
  const key = getShareKey();
  if (!key) return `${BASE}${path}`;
  const sep = path.includes("?") ? "&" : "?";
  return `${BASE}${path}${sep}key=${encodeURIComponent(key)}`;
};
