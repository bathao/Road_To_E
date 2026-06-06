# Progress Log — Table Tennis Coach

## Current status (2026-06-06)

**Tab 1 "Daily Tracker" is feature-complete; Tab 2 "Tactical Playbook" v1 is in.**
Stack: FastAPI + SQLite backend, React + Vite + TS frontend, served on one port
by `start.bat`.

**Tab 2 "Tactical Playbook"** — a tactic knowledge base with two areas: *My
Tactics* (the user's own playbook — manual add or copied up from the Library;
full CRUD, confidence stars, favourite, tags) and a built-in *Library* of ~40
general tactics (browse-only; "↑ Add to My Tactics" copies one up, tracked via
`source_key`). Organised by 5 phases (Serve / Return / Third ball / Rally /
Chung), one phase selector + search / opponent / favourite filters drive both
areas. 18 Library tactics carry a source link (PingSunday, Tom Lodziak,
Killerspin, Samson Dubina). Content mixes English jargon with Vietnamese.

Working features:
- Excel-like weekly grid; one shared timeline (Day / Week / Month / Year /
  Custom + ◀ Today ▶) drives both the grid and the Analysis panel.
- **Duration** rows → one-tap chips (+ custom + note).
- **Match** rows → dropdown score picker (Singles/Doubles, BO3/5/7), event
  autocomplete, Travel/Rest; each set score is one match record.
- **Physical Training** → checklist (Wall Sit, Sit-ups, Plank, Squats, Obliques,
  Stretching); cell turns yellow at ≥70% ticked.
- **Overall** is auto-generated per day: green (a green-row trained), else yellow
  (any other data), else red (a past tracked day with no data), else blank
  (today not yet logged / future / before tracking began).
- Future days are not editable. App opens on the latest week that has data.
- **Analysis panel**: summary cards (days trained, physical days, training time,
  Singles / Doubles / All-matches win rates) + a comparison chart (Columns or
  Line, default Line; metric selector) + training-time-by-category bars.
- Excel / CSV export of the selected range.
- **Coaching packages**: coaching is bought in 10-session blocks; the first
  session of a block is marked with ★ (`is_package_start`). `/coach-packages`
  reports current + historical blocks (used / remaining / over, status
  ok·low·done·over); `/coach-package-start-allowed` guards which days may open a
  new block (session 1, or the 11th-or-later of the current block).

**Released:** v0.1 (initial Daily Tracker), v0.2 (block future days + track the
personal DB in git), v0.3 (shared timeline, Analysis comparison charts,
auto-red Overall, full Mar–Jun import, coaching packages).

---

## Data

The DB (`backend/data/tabletennis.db`) is tracked in git on purpose (personal
data). It currently holds continuous imported history **1 Mar – 1 Jun 2026**
(the former 9–22 Mar gap is now filled). Imported via one-off
`backend/scripts/imports/import_*.py` scripts (idempotent, each wipes its own
date range; Overall is never imported).

Import mapping decisions (with the user): matches split by `D:` into doubles,
W/L from sets; event names kept (Mai Lượng, Giải Vi Mạch, Giải Đồng đội 185,
Giải FS, BBTV…); Travel/"sets (cty)" → non-playing/skip; Serve counts → minutes
(~200 serves ≈ 15 min); Wall Sit → Physical `wall_sit` tick; "W1 L4" summary →
1 win + 4 losses with placeholder 3-0/0-3 scores.

---

## History

### 2026-06-06 — v0.4: Tab 2 "Tactical Playbook"
- New backend feature `app/features/playbook/` (model `playbook_tactic`, schemas,
  service, router at `/api/playbook`, static `library.py` catalog) wired via the
  registry; table auto-created by `create_all` (no migration).
- New frontend tab `tabs/tactical-playbook/` (My Tactics + Library sections, phase
  selector, filters, `TacticCard`, `TacticEditor`); promoted `Modal` to
  `shared/ui/Modal.tsx` and repointed daily-tracker's import.
- Library content researched from reputable coaching sources (WebSearch/WebFetch
  done inline — the background workflow stalled on tool-permission denial) and
  given per-tactic `source` / `source_url`. Card labels: When / How / Next / Risk.
- Card/editor polish: 2-column field layout, cards size to content, wider modal
  for the tactic form, wrapping phase chips (fixed the editor's horizontal
  overflow).

### 2026-06-06 — v0.3
- Coaching packages: new `Activity.is_package_start` column (+ one-off migration
  `scripts/migrations/add_coach_package_marker.py` backfilling the old "N" note
  convention); `compute_coach_packages` / `coach_package_start_allowed` service
  logic; `/coach-packages` + `/coach-package-start-allowed` endpoints; ★ shown
  on the first session of each block in the grid.
- Grid now spans an arbitrary range: `build_week`/`/weeks` take an optional
  `end` (defaults to a 7-day week); `monthGroups` helper for a month-grouping
  header row (Year grid). Physical cell uses a `·` divider instead of newlines.
- Filled the former 9–22 Mar gap (`import_mar_gap2026.py`) → continuous
  1 Mar – 1 Jun 2026 history.

### 2026-06-01 — v0.1
- Backend `tracker` feature (models, seed, schemas, service, router) + `core/`;
  frontend AppShell + tab registry + daily-tracker tab; `start.bat`; README.
- Refinements: removed "Other Training/Physical" rows (seed is now a reconcile);
  Overall became auto-generated (filled cell, not a manual dot); Physical Training
  became a checklist (`tracker_physical_check` + `/physical-items`,
  `/physical-checks`); inline Analysis panel (`/stats`); grid styling polish.

### 2026-06-02 — v0.2 + (uncommitted work)
- v0.2: block future-day input; track the personal DB in git.
- Analysis: Year mode + `/breakdown`; comparison chart (Columns/Line, metric
  selector, YouTube-style line tooltip); Month columns labelled "Week 1..N".
- Shared timeline: one `PeriodControl` (logic in `period.ts`) drives the grid
  and Analysis together; app opens on the latest week with data (`/last-date`).
- Overall: empty past days (within the tracked range) now show red.
- Removed the Analysis "By day" table; cleaned the dead code it left behind.
- Incident: accidentally deleted the user's 2026-06-01 manual entry while
  clearing test data — restored it. Rule recorded: never delete tracker rows.

---

## Run

`start.bat` (build + serve + open Chrome), or backend alone:
`cd backend && .venv\Scripts\python -m uvicorn app.main:app --reload --port 8000`.
