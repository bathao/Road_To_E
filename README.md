# Road To E 🏓

A local web tool that acts as a personal table tennis coach on the road from
rank G to rank E: plan, log daily activity, analyze, and track progress. Built
one tab at a time on an extensible multi-tab architecture.

- **Backend:** FastAPI + SQLite (`backend/`)
- **Frontend:** React + Vite + TypeScript + plain CSS (`frontend/`)
- Served on a single port (8000); the FastAPI app also serves the built SPA.
- UI is English; the AI coach converses in Vietnamese.

## Quick start (Windows)

Double-click **`start.bat`** (or run it from a terminal). On first run it:

1. Creates the backend virtual environment and installs Python deps.
2. Installs frontend npm deps.
3. Rebuilds the frontend fresh (clears the old `dist`).
4. Starts the server on `http://localhost:8000` and opens a new Chrome tab.

Press `Ctrl+C` in the terminal to stop the server.

### Prerequisites for the AI coach

The **Coach** tab talks to a local LLM via **Ollama** (all AI runs locally, no
network): install Ollama, then `ollama pull qwen3.5:9b` (the verdict/chat
model; it falls back to `qwen3:14b` if not pulled — see
`backend/app/core/settings.py`). Every other tab works without Ollama.

## Tabs

- **📅 Daily Tracker** — the core. An Excel-like grid on a shared timeline
  (Day / Week / Month / Year / Custom):
  - Duration rows (Train with Coach, Backhand with Partner, Serve) → one-tap
    chips; coach sessions group into 10-session packages with a renewal card.
  - Physical Training → checklist, or auto-filled from the Training Center.
  - Match rows (Practice / Official / Tournament) → Singles / Doubles / 1v2 /
    2v1, BO3/5/7, score picker, opponents/partner from the player pool,
    per-set handicap patterns, tournament link + round, per-match ±ELO chip.
    No typing. Tournaments have a **format**: Tournament (group → knockout
    rounds, ☠ knocked-out, derived placements) or **League** (a round-robin
    block of 3–5 matches; no rounds, no elimination, W–L is the result).
  - Coach & Recap row → structured items per coach-session day (advice with
    a done-lifecycle, numbered drills, session recaps) — feeds the AI coach.
  - Overall row → auto color; day notes; upcoming-tournament strip + section
    (entering a tournament's results retires its card — played history lives
    in the Profile tab).
  - Analysis panel under the grid: comparison chart + ELO curve on the SAME
    day axis, day/minute/racket-time summary cards; Excel/CSV export. (Match
    win-rate stats live in the Profile tab, where every KPI tile clicks
    through to the exact matches behind it.)
- **🧠 Coach** — a strict Vietnamese head coach backed by a local LLM. Reads
  ONLY database facts (volume, matches with opponent context, ELO trend,
  physical load, day notes, real-life coach's advice, upcoming tournaments).
  Two views: **Verdict** (holistic assessment + measurable weekly directives
  tracked live against real data + a week plan) and **Recaps** (on-demand
  review of the last 7 or 30 days vs the window before); grounded chat with
  an auto-written notebook.
- **🪪 Profile** — my dynamic ELO (the only dynamic rating: anchor + replay)
  with the since-anchor curve + per-match ELO table, win rates and
  head-to-head per opponent, training snapshots — all over a YouTube-style
  range picker (rolling last-N-days / Lifetime / year / month / custom), and
  the Tournament Record (played tournaments: result reached, W-L, every
  match — all derived from the grid).
- **💪 Training Center** — knee-safe (grade-1 osteoarthritis) physical
  program: leveled day templates, workout player, progressive targets with
  pain/RPE autoregulation, weekly summary.
- **🗄️ Database** — the player pool: every opponent/partner with static
  points (maintained by hand), auto rank chip, pips flag.
- 🔥 Motivation — placeholder ("coming soon").

## Sharing with the coach (read-only copy)

The Daily Tracker, Profile and Journal tabs can be published as a **read-only
copy** on Render's free tier so the real-life coach can follow along — no AI,
no editing, same GUI. It is the same app started with `SHARE_MODE=1`
(`backend/app/core/share.py`):

- every non-GET call under `/api/` is refused with 403, the GUI hides the
  other tabs and shows a "Read-only view · Last synced …" banner, and the
  API client refuses writes before they leave the browser;
- optional `SHARE_KEY`: the coach types the code once (remembered in the
  browser; the export link carries it as `?key=`);
- the on-startup backup is skipped (the host's disk is ephemeral).

Live copy: **https://road-to-e.onrender.com** (no access code by choice).
The data on the shared copy is the committed `backend/data/tabletennis.db`.
**Syncing = the ☁ Sync to coach button** in the local header (`POST /api/sync`,
`backend/app/core/syncer.py`) or, as a fallback, `sync.bat`. Both checkpoint the WAL (so the committed file is
never stale), stamps `backend/data/last_sync.txt`, commits ONLY those two
files and push; Render rebuilds the Docker image (~1 min). The button then
polls the shared copy's `/api/config` until the new `last_sync` shows up
there and reports "Live for the coach". `render.yaml`
is the Blueprint (Docker runtime, Singapore, health check `/api/health`);
`Dockerfile` builds the SPA with Node and runs uvicorn on python:3.12-slim.
A free web service sleeps after 15 idle minutes (~1 min to wake) — an
external pinger on `/api/health` every ~10 min keeps it awake within the
750 free hours/month.

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

Backend tests (pytest comes from the dev requirements, not `start.bat`):

```bash
cd backend
.venv\Scripts\python -m pip install -r requirements-dev.txt   # first time
.venv\Scripts\python -m pytest tests -q
```

## Architecture

Feature-based modularity so adding a tab = one folder + one registry line.

- **Backend:** `app/features/<feature>/` (router/models/schemas/service/seed);
  `app/features/registry.py` collects routers; `app/main.py` includes them all.
  DB tables are namespaced per feature (`tracker_*`) to avoid collisions.
  Retired features (Tactical Playbook, Video Analysis) keep their tables in
  the DB — user data is never deleted.
- **Frontend:** `src/tabs/<tab>/`; `src/tabs/registry.ts` declares each tab;
  `AppShell` builds the tab bar. Shared helpers/UI live in `src/shared/`.
- The SQLite DB (`backend/data/tabletennis.db`) is tracked in git on purpose;
  a daily snapshot also lands in `backend/data/backups/` on startup. The committed
  file is also what the shared read-only copy serves (see above).

See `PROGRESS.md` for the live status log (newest first), `TODO.md` for open
items, and `PLAN.md` for the original Tab-1 design (historical).
