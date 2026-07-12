# Table Tennis Coach

A local web tool that acts as a personal table tennis coach: plan, log daily
activity, analyze, and track progress. Built one tab at a time on an extensible
multi-tab architecture.

- **Backend:** FastAPI + SQLite (`backend/`)
- **Frontend:** React + Vite + TypeScript + plain CSS (`frontend/`)
- Served on a single port (8000); the FastAPI app also serves the built SPA.

## Quick start (Windows)

Double-click **`start.bat`** (or run it from a terminal). On first run it:

1. Creates the backend virtual environment and installs Python deps.
2. Installs frontend npm deps.
3. Rebuilds the frontend fresh (clears the old `dist`).
4. Starts the server on `http://localhost:8000` and opens a new Chrome tab.

Press `Ctrl+C` in the terminal to stop the server.

## Tabs

- **Daily Tracker** (built) — an Excel-like weekly grid. Click any cell to log:
  - **Duration** rows (Train with Coach, Backhand, Serve) → one-tap chips
    (15m/30m/1h…) or a custom value.
  - **Physical Training** → a checklist of exercises; the cell turns yellow once
    ≥70% are ticked.
  - **Match** rows (Practice / Official) → pick Singles/Doubles + BO3/BO5/BO7,
    then tap a final score (wins green, losses red). No score typing. Event
    autocomplete and Travel/Rest quick buttons included.
  - **Overall** row → auto-generated color: green (trained a key skill), yellow
    (other activity), red (a past day with nothing logged).
  - One shared timeline (Day / Week / Month / Year / Custom) drives the grid and
    the **Analysis panel** below it (summary cards + comparison Columns/Line chart).
  - Export the selected range to **Excel** or **CSV** from the toolbar.
- Training Plan / Motivation — placeholders ("coming soon").

## Development

Run backend and frontend dev servers separately for hot reload:

```bash
# Backend (terminal 1)
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Frontend (terminal 2) — Vite proxies /api to the backend
cd frontend
npm run dev   # http://localhost:5173
```

After changing backend Pydantic schemas, regenerate the TypeScript API types
(used to check the hand-written mirrors in `src/tabs/*/types.ts` for drift):

```bash
cd frontend
npm run gen:api   # -> src/shared/api/schema.d.ts (from FastAPI's OpenAPI)
```

Backend tests:

```bash
cd backend
.venv\Scripts\python -m pytest tests -q
```

## Architecture

Feature-based modularity so adding a tab = one folder + one registry line.

- **Backend:** `app/features/<feature>/` (router/models/schemas/service/seed);
  `app/features/registry.py` collects routers; `app/main.py` includes them all.
  DB tables are namespaced per feature (`tracker_*`) to avoid collisions.
- **Frontend:** `src/tabs/<tab>/`; `src/tabs/registry.ts` declares each tab;
  `AppShell` builds the tab bar. Disabled tabs render `ComingSoon`.

See `PLAN.md`, `TODO.md`, and `PROGRESS.md` for details and status.
