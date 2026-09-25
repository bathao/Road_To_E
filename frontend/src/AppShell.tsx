import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { TABS, type TabDef } from "./tabs/registry";
import ComingSoon from "./tabs/ComingSoon";
import {
  checkShareKey,
  getShareKey,
  loadConfig,
  setShareKey,
  SHARED_TAB_IDS,
  type AppConfig,
} from "./shared/config";
import { prettyDate } from "./shared/dates";

// Top-level layout: a tab bar driven by the registry plus the active tab body.
// A plain useState (not a router) keeps the build dependency-free.
//
// Boot sequence (2026-09-25): GET /api/config first. Locally it says
// share_mode=false and the shell renders exactly as before. On the shared
// read-only host it hides the tabs that need local AI / are the player's own
// tooling, shows the "Read-only view" banner and, when the server demands an
// access code, asks for it once (remembered in localStorage).
export default function AppShell() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  // null = not checked yet; false = code required and not (correctly) known.
  const [unlocked, setUnlocked] = useState<boolean | null>(null);

  useEffect(() => {
    let alive = true;
    loadConfig().then(async (cfg) => {
      if (!alive) return;
      setConfig(cfg);
      if (!cfg.key_required) {
        setUnlocked(true);
        return;
      }
      const known = getShareKey();
      const ok = known ? await checkShareKey(known) : false;
      if (!ok) setShareKey(null);
      if (alive) setUnlocked(ok);
    });
    return () => {
      alive = false;
    };
  }, []);

  if (config === null || unlocked === null) {
    return <div className="app-boot">Loading…</div>;
  }
  if (!unlocked) {
    return <ShareKeyGate onUnlock={() => setUnlocked(true)} />;
  }

  const tabs = config.share_mode
    ? TABS.filter((t) => SHARED_TAB_IDS.has(t.id))
    : TABS;
  return (
    <Shell
      tabs={tabs}
      shareMode={config.share_mode}
      banner={config.share_mode ? <ShareBanner lastSync={config.last_sync} /> : null}
    />
  );
}

function Shell({
  tabs,
  shareMode,
  banner,
}: {
  tabs: TabDef[];
  shareMode: boolean;
  banner: ReactNode;
}) {
  const firstEnabled = tabs.find((t) => t.enabled) ?? tabs[0];
  const [activeId, setActiveId] = useState(firstEnabled.id);

  const active = tabs.find((t) => t.id === activeId) ?? firstEnabled;
  const Body = active.component;

  return (
    <div className={`app-shell${shareMode ? " share-mode" : ""}`}>
      <header className="app-header">
        {banner}
        <div className="app-title">
          <span className="app-logo">🏓</span>
          <span>Road To E</span>
        </div>
        <nav className="tab-bar">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={`tab-btn${tab.id === activeId ? " active" : ""}${
                tab.enabled ? "" : " disabled"
              }`}
              onClick={() => setActiveId(tab.id)}
              title={tab.enabled ? tab.label : `${tab.label} (coming soon)`}
            >
              <span className="tab-icon">{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </header>
      <main className="app-body">
        {active.enabled ? <Body /> : <ComingSoon label={active.label} />}
      </main>
    </div>
  );
}

// "2026-09-25T20:15" → "25 Sep 2026, 20:15" (the sync PC's local time).
function fmtSync(iso: string): string {
  const [date, time] = iso.split("T");
  return time ? `${prettyDate(date)}, ${time}` : prettyDate(date);
}

function ShareBanner({ lastSync }: { lastSync: string | null }) {
  return (
    <div
      className="share-banner"
      title="This is a published copy of the player's data. Nothing can be edited here; the player syncs new data from their own PC."
    >
      <span className="share-banner-icon">👁</span>
      <span>
        <strong>Read-only view</strong> · shared by the player for the coach
      </span>
      <span className="share-banner-sync">
        {lastSync ? `Last synced ${fmtSync(lastSync)}` : "Sync time unknown"}
      </span>
    </div>
  );
}

function ShareKeyGate({ onUnlock }: { onUnlock: () => void }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = code.trim();
    if (!trimmed) return;
    setBusy(true);
    const ok = await checkShareKey(trimmed);
    setBusy(false);
    if (ok) {
      setShareKey(trimmed);
      onUnlock();
    } else {
      setError("Wrong access code.");
    }
  };

  return (
    <div className="share-gate">
      <form className="share-gate-card" onSubmit={submit}>
        <div className="share-gate-logo">🏓</div>
        <h1>Road To E</h1>
        <p>
          This is a read-only view shared by the player. Enter the access code
          you were given to open it.
        </p>
        <input
          type="password"
          autoFocus
          autoComplete="off"
          placeholder="Access code"
          value={code}
          onChange={(e) => {
            setCode(e.target.value);
            setError(null);
          }}
        />
        {error && <div className="share-gate-error">{error}</div>}
        <button className="btn primary" type="submit" disabled={busy || !code.trim()}>
          {busy ? "Checking…" : "Open"}
        </button>
      </form>
    </div>
  );
}
