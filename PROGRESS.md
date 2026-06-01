# Progress Log — Table Tennis Coach

## 2026-06-01
- Project kickoff. Plan approved (see `PLAN.md`).
- Decisions locked: SQLite + Excel/CSV export, local web (FastAPI + React/Vite/TS), English UI,
  multi-tab extensible architecture, `start.bat` launcher (clear cache + open new Chrome tab).
- Match input refined: dropdown-driven (Singles/Doubles + BO3/BO5/BO7, default BO5 + score picker);
  the `D: W(3-1,3-2)` string is for display/export only, never typed by hand.
- DB designed extensible: tables namespaced per feature (`tracker_*`) so future tabs (tactics,
  supplementary drills, ...) add their own tables without collisions.
- Convention: docs/code/comments/GUI in English; spoken explanations to the user in Vietnamese.

### Backend — DONE and verified
- `backend/` built: `core/` (settings, base, db), `features/registry.py`, `app/main.py`.
- Feature `tracker`: `models.py` (Category, Activity, Event, Match[+best_of], DayRating),
  `seed.py` (9 categories), `schemas.py`, `service.py` (duration + match-string formatting,
  week aggregation, CSV/XLSX export), `router.py` (categories, weeks, activities upsert, matches
  CRUD, ratings upsert, events autocomplete, export).
- Deps installed into `backend/.venv` from `requirements.txt`.
- Smoke test passed: `app.main` imports, `init_db()` + seeds run, 9 categories present.
- Note: `backend/data/tabletennis.db` was created during the smoke test (safe to keep or delete).

### Frontend — DONE and verified
- `frontend/` scaffolded by hand (no interactive `npm create`): `package.json`,
  `vite.config.ts` (base `./`, `/api` dev proxy), `tsconfig*`, `index.html`, `src/main.tsx`.
- `AppShell.tsx` + `tabs/registry.ts` + `tabs/ComingSoon.tsx`. Tab switching uses a
  plain `useState` instead of React Router (dependency-free, reliable build).
- `tabs/daily-tracker/`: `types.ts` (mirrors backend schemas), `api.ts`, `dates.ts`
  (local-day helpers, Monday-start weeks), `scores.ts` (valid BO3/5/7 final scores).
- Components: `WeekNav`, `WeekGrid` (sticky category column, today highlight),
  `Modal`, and editors `DurationEditor` (chips + custom + note), `MatchEditor`
  (discipline/format toggles, win/loss score picker, event autocomplete via
  `<datalist>`, Travel/Rest, existing-match list with delete), `RatingEditor`.
- `styles.css`: Excel-like grid, color-group row headers (green/yellow), modal, pickers.
- `npm install` + `npm run build` succeed (fixed `tsconfig.node.json` emit error).

### Launcher + docs — DONE
- `start.bat`: first-run dep install (venv + npm), fresh `dist` rebuild, uvicorn on
  127.0.0.1:8000, opens a new Chrome tab after a short boot delay.
- `README.md` written (quick start, dev mode, architecture).

### End-to-end verification — PASSED
Ran uvicorn and exercised the full stack:
- `/api/health` ok; `/categories` returns the 9 seeds.
- PUT activity (90m + note), POST two matches (singles W 3-1, doubles L 2-3, same
  event), PUT rating green → week `cells` rendered correctly:
  `1 hour 30 mins (footwork)`, `BBTV Open\nW(3-1)\nD: L(2-3)`, rating `green`.
- `/events?q=BB` autocomplete returns the created event.
- `/export?format=xlsx` returns the right content-type/disposition (5.4 KB file).
- SPA: `/` serves built `index.html`; `/assets/*.js` serves with 200 + js mime.
- Test data deleted afterwards (DB clean; one harmless `BBTV Open` event remains
  for autocomplete).

### Tab 1 refinements (post-build, verified)
- Removed two rows: "Other Training with Partner" and "Other Physical Activities".
  `seed_categories` is now a reconcile (drops stale categories + their entries).
- "Overall" is no longer a manual input — it is auto-generated per day
  (`service.compute_overall_colors`): green if any of the 3 green rows has data,
  else yellow if any remaining row has data. The whole cell is filled with the
  color (no dot). Applies on-grid and in export.
- "Physical Training" is now a checklist (type `checklist`), not a duration.
  Items (English): Wall Sit, Sit-ups, Plank, Squats, Obliques, Stretching
  (`service.PHYSICAL_ITEMS`). New table `tracker_physical_check`; endpoints
  `GET /physical-items`, `PUT /physical-checks`. The cell lists ticked items and
  fills yellow once >=70% are ticked (`PHYSICAL_YELLOW_RATIO`). Verified: 4/6 not
  yellow, 5/6 yellow; export xlsx fills match.

### Analysis panel (under the grid) — verified
- New `GET /api/tracker/stats?from=&to=` (`service.build_stats`) — no schema change,
  everything derived from existing tables.
- `AnalysisPanel` rendered below the WeekGrid in the Daily Tracker tab, with its own
  period selector: Day / Week / Month (◀ Today ▶) + a Custom from–to range.
- Shows: days trained (X/N), physical days, total training time; Singles / Doubles /
  All-matches cards (win rate, W-L-T, sets won–lost); minutes-by-category bars; and a
  per-day table (trained ✅, physical 🟡 count, matches, time) answering "which days
  had physical / training and which didn't". Auto-refreshes after any grid edit
  (`dataVersion` signal). Verified against seeded data: singles 1-1 (50%),
  doubles 1-0 (100%), overall 2-1 (67%), 3 days trained, 1 physical day.

### Design polish
- Grid content centered (both axes), taller rows; softened green/yellow row headers
  (light tint + left accent bar); centered the Category column.

### Resume next
Tab 1 is functionally complete (grid + checklist + auto Overall + inline Analysis).
Optional: speedups (Copy yesterday / Repeat last week), charts in the Analysis panel,
then begin a future tab.
Run everything with `start.bat`, or backend alone:
`cd backend && .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000`.
