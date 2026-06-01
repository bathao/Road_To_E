import { useState } from "react";
import { TABS } from "./tabs/registry";
import ComingSoon from "./tabs/ComingSoon";

// Top-level layout: a tab bar driven by the registry plus the active tab body.
// A plain useState (not a router) keeps the build dependency-free.
export default function AppShell() {
  const firstEnabled = TABS.find((t) => t.enabled) ?? TABS[0];
  const [activeId, setActiveId] = useState(firstEnabled.id);

  const active = TABS.find((t) => t.id === activeId) ?? firstEnabled;
  const Body = active.component;

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-title">
          <span className="app-logo">🏓</span>
          <span>Table Tennis Coach</span>
        </div>
        <nav className="tab-bar">
          {TABS.map((tab) => (
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
