import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { prettyDate } from "../dates";

// "Sync to coach" (2026-09-25) — local machine only. One click = checkpoint
// the DB, commit the snapshot + stamp, push; Render rebuilds the shared
// copy (~1 min). After a push we poll <share_url>/api/config until its
// last_sync matches ours, so the player knows the coach really sees the
// new data without opening the Render dashboard.

interface SyncOut {
  status: "pushed" | "nothing";
  commit?: string | null;
  stamp: string | null;
  counts: Record<string, number>;
}

type Phase =
  | { kind: "idle" }
  | { kind: "syncing" }
  | { kind: "nothing" }
  | { kind: "pushed"; stamp: string } // waiting for the shared copy
  | { kind: "live"; stamp: string }
  | { kind: "error"; message: string };

const POLL_MS = 15_000;
const POLL_MAX_MS = 6 * 60_000; // Render build (~1 min) + a sleeping host (~1 min) + slack

// "2026-09-25T20:13:49" → "25 Sep 2026, 20:13"
function fmtStamp(iso: string): string {
  const [date, time] = iso.split("T");
  return time ? `${prettyDate(date)}, ${time.slice(0, 5)}` : prettyDate(date);
}

// The host reports minutes; ours has seconds — compare on the minute.
const sameMinute = (a: string | null, b: string | null) =>
  !!a && !!b && a.slice(0, 16) === b.slice(0, 16);

export default function SyncButton({
  initialLastSync,
  shareUrl,
}: {
  initialLastSync: string | null;
  shareUrl: string | null;
}) {
  const [lastSync, setLastSync] = useState<string | null>(initialLastSync);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const pollTimer = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollTimer.current !== null) {
      window.clearTimeout(pollTimer.current);
      pollTimer.current = null;
    }
  };
  useEffect(() => stopPolling, []);

  // Poll the shared copy until it serves our stamp (or give up quietly).
  const waitForLive = (stamp: string) => {
    if (!shareUrl) return;
    const started = Date.now();
    const tick = async () => {
      try {
        const res = await fetch(`${shareUrl}/api/config`, { cache: "no-store" });
        if (res.ok) {
          const cfg = (await res.json()) as { last_sync: string | null };
          if (sameMinute(cfg.last_sync, stamp)) {
            setPhase({ kind: "live", stamp });
            return;
          }
        }
      } catch {
        /* host asleep / rebuilding — keep polling */
      }
      if (Date.now() - started < POLL_MAX_MS) {
        pollTimer.current = window.setTimeout(tick, POLL_MS);
      }
      // Past the budget we simply stay in "pushed": the push itself is done.
    };
    pollTimer.current = window.setTimeout(tick, POLL_MS);
  };

  const sync = async () => {
    stopPolling();
    setPhase({ kind: "syncing" });
    try {
      const out = await api.post<SyncOut>("/sync", {});
      if (out.status === "nothing") {
        setPhase({ kind: "nothing" });
        if (out.stamp) setLastSync(out.stamp);
        return;
      }
      const stamp = out.stamp ?? new Date().toISOString();
      setLastSync(stamp);
      setPhase({ kind: "pushed", stamp });
      waitForLive(stamp);
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      // "500 Internal Server Error: {"detail":"..."}" → just the detail.
      let message = raw;
      const m = raw.match(/"detail":"([\s\S]*)"}$/);
      if (m) message = m[1].replace(/\\n/g, "\n").replace(/\\"/g, '"');
      setPhase({ kind: "error", message });
    }
  };

  const busy = phase.kind === "syncing";
  let status: React.ReactNode;
  switch (phase.kind) {
    case "syncing":
      status = <span className="sync-status">Checkpoint · commit · push…</span>;
      break;
    case "nothing":
      status = (
        <span className="sync-status">
          Nothing new since {lastSync ? fmtStamp(lastSync) : "the last sync"}
        </span>
      );
      break;
    case "pushed":
      status = (
        <span className="sync-status sync-wait">
          Pushed · the shared copy is rebuilding (~1 min)…
        </span>
      );
      break;
    case "live":
      status = <span className="sync-status sync-live">✓ Live for the coach</span>;
      break;
    case "error":
      status = (
        <span className="sync-status sync-error" title={phase.message}>
          ✕ {phase.message.split("\n")[0]}
        </span>
      );
      break;
    default:
      status = (
        <span className="sync-status">
          {lastSync ? `Last synced ${fmtStamp(lastSync)}` : "Never synced"}
        </span>
      );
  }

  return (
    <div className="sync-box">
      <button
        className="btn sync-btn"
        onClick={sync}
        disabled={busy}
        title="Publish the current database to the shared read-only copy for the coach (commit + push; Render rebuilds in about a minute)"
      >
        ☁ {busy ? "Syncing…" : "Sync to coach"}
      </button>
      {status}
    </div>
  );
}
