# TODO — Table Tennis Coach

Status legend: [ ] pending · [~] in progress · [x] done

## Tab 1 — Daily Tracker (current)
- [x] Backend foundation: `core/` (db, base, settings), `features/registry.py`, `main.py`
- [x] Tracker backend: `models.py`, `seed.py` (9 default categories), `schemas.py`, `service.py`
- [x] Tracker router: weeks, activities, matches, ratings, events, export
- [x] Backend deps installed + smoke test (imports OK, 9 categories seeded)
- [x] Frontend foundation: Vite React TS, `AppShell`, tab registry, `ComingSoon` (tab state, no router)
- [x] Daily-tracker tab: WeekGrid, WeekNav, cells, editors (duration/match/rating)
- [x] Match editor (dropdown-driven): Singles/Doubles + BO3/BO5/BO7 (default BO5) + score picker
- [x] Export UI + Excel/CSV download buttons
- [x] `start.bat`: install deps, fresh build (clear cache), run uvicorn, open new Chrome tab
- [x] End-to-end verification (build + all API endpoints + SPA serving exercised)
- [ ] Speedups: Quick add Today, Copy yesterday, Repeat last week (deferred — needs design)

## Resume here next
Tab 1 is functionally complete. Optional polish before moving to Tab 2:
1. Speedups (Copy yesterday / Repeat last week) — likely client-side replication
   via existing endpoints, or add backend bulk-copy endpoints.
2. Manual UI pass in the browser (open via `start.bat`) to sanity-check styling.
Then start Tab 2 (Analysis) per the feature-module + tab-registry pattern.

## Future tabs (not started)
- [ ] Analysis / charts
- [ ] Training Plan
- [ ] Motivation / goals
- [ ] Tactics, supplementary drills (will add their own `*_` tables — DB is namespaced per feature)
