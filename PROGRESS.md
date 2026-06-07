# Progress Log — Table Tennis Coach

## Current status (2026-06-07)

**Four tabs in place.** Tab 1 "Daily Tracker" feature-complete; Tab 2 "Tactical
Playbook" v1; Tab 3 "Match Stats" (named-opponent analytics); Tab 4 "Video
Analysis" — local-AI clip analysis (new, this session). Stack: FastAPI + SQLite
backend, React + Vite + TS frontend, served on one port by `start.bat`. The
backend venv is now **Python 3.12** (mediapipe ships no 3.13 wheels); `start.bat`
builds it with `py -3.12`.

**Tab 4 "Video Analysis"** — point the tab at a video file on disk (local-only,
no browser upload), optionally give a trim range (mm:ss) to cut a short segment
out of a long recording with `ffmpeg`; only the cut is kept as material in
`backend/data/videos/`. The clip is then analysed locally: `ffmpeg`/OpenCV sample
~14 frames → MediaPipe pose (stance width, knee flexion, torso lean, lateral
sway, hand height) → a vision-language model via Ollama (`qwen3-vl:8b` by
default, switchable; runs on the RTX 5060 Ti 16GB) returns a Vietnamese coaching
analysis (strengths / weaknesses / serve / footwork / posture / drills) as
structured JSON. The DB revolves around the player **Nguyễn Bá Thảo**: a singleton
`va_profile` (basics + AI-maintained summaries), `va_clip`, `va_analysis`,
`va_trait` (strength/weakness observations that accumulate across clips and can
be folded back into the profile by a local text model), and `va_profile_image`
(the identity gallery). Honest limit: a general VLM is an assistant, not a
biomechanics judge — short clips with the player in frame work best.

**Self-learning identity ("which one is me").** A match clip has two players, so
the pipeline must know which is Nguyễn Bá Thảo before analysing. It runs in
**two steps with a confirmation gate**: step 1 the VLM *only detects* the subject
(using any user-given side/appearance label + the reference gallery), reports its
guess with a cropped preview, and the user confirms (`✓ Đúng là tôi`), corrects
the label, or **draws a box** around themselves on the full frame. Only after
confirmation does step 2 run the deep analysis. Crops of the confirmed player are
saved to `backend/data/profile_refs/` + `va_profile_image`, so later clips are
identified automatically; if the model is unsure it sets `needs_id` and asks.
States: `pending → processing(detect) → awaiting_confirm | needs_id →
analyzing → done | error`. The native file picker is per-monitor-v2 DPI-aware so
the dialog is crisp on scaled displays.

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

### 2026-06-07 — Tab 4 "Video Analysis" (local AI: VLM + pose) + 3 new players
- New backend feature `app/features/video_analysis/` (models `va_profile`,
  `va_clip`, `va_analysis`, `va_trait`; schemas; `analyzer.py`; service; router at
  `/api/video`; `seed.py` for the Nguyễn Bá Thảo profile) wired via the registry;
  tables auto-created by `create_all` (no migration, existing data untouched).
- `analyzer.py` pipeline: `ffmpeg` trim of a chosen [start,end] segment →
  OpenCV frame sampling → MediaPipe pose metrics → Ollama `/api/chat` VLM call
  with a JSON-schema structured output and `num_ctx=32768` (14 frames ≈ 14.7k
  tokens — the 4096 default 400'd until raised). Vietnamese coach prompt. A
  text-model path (`qwen3:14b`) synthesises the profile summaries from traits.
- New frontend tab `tabs/video-analysis/` (ProfilePanel, TraitBoard, UploadForm,
  ClipList, AnalysisDetail; api/types/labels) registered in `tabs/registry.ts`
  (icon 🎬). Polls while clips are processing. Regenerate-summary button disabled
  until traits exist.
- **Local-only**: clips come from a file path on disk (browser upload removed at
  the user's request); the create endpoint takes JSON. Source file is never
  modified; only the trimmed cut is stored.
- Env: recreated the project venv on **Python 3.12** and added `httpx`,
  `python-multipart`, `opencv-python`, `mediapipe`, `numpy`; `start.bat` now uses
  `py -3.12`; `backend/data/videos/` gitignored.
- Two bugs found & fixed in verification: Ollama 400 from the 4096 context cap
  (→ `num_ctx`), and a 500 from `model_validate` eager-loading the analysis
  relationship (→ map `raw`/`pose` by hand). UX fix: 502 on regenerate-summary
  with no traits → button now disabled.
- Added 3 opponents to the DB (Lai / Thêm / Tùng "Ampere", level below).
- **Self-learning identity** (vòng lặp tự học): new `va_profile_image` gallery +
  `va_clip` columns (`me_side`, `me_appearance`, `subject_desc`, `identified`,
  `preview_path`) via an idempotent `migrate()` (PRAGMA + ALTER, existing rows
  kept). Two-step pipeline split into `detect_clip` (light VLM detect, DETECT
  schema) → confirmation gate → `analyze_clip` (deep). `analyzer.py` gained
  `crop_side`, `_tighten_to_person` (pose bbox only if ≥15% of the half-crop,
  else keep the half — fixed a preview that latched onto a wall), `detect_subject`,
  `make_preview_b64`, `subject_crops`, `frame_jpeg`, `crop_box_jpeg`. New endpoints:
  `/profile/images` (CRUD + `/file`), `/clips/{id}/{confirm,identify,detect,frame,
  preview,crop-reference}`. Front-end: `BoxAnnotator` (drag a normalised 0..1 box
  on the full frame), awaiting-confirm panel (preview + 3 buttons), reference
  gallery in `ProfilePanel`.
- DPI fixes for the native picker: `SetProcessDpiAwarenessContext(-4)`
  (per-monitor-v2) in the Tkinter subprocess prelude — crisp on the 150%-scaled
  display (root cause of the lingering blur was two stale uvicorn servers running
  old code on :8000; killed both). Preview thumbnail cache-busting (`?v=N`) so a
  re-saved crop at the stable `/preview` URL refetches.

### 2026-06-06 — Opponents/players DB + match-entry redesign
- New `tracker_player` table (shared opponent/partner pool: `name`, relative
  `level` below/equal/above, `note`) + `/players` CRUD (search / get-or-create /
  update), mirroring the Event idiom. Migration
  `scripts/migrations/add_match_opponents.py` adds the table + four `tracker_match`
  columns (`opponent_id`, `opponent2_id`, `partner_id`, signed `handicap`).
- `MatchEditor` redesigned: a `PlayerPicker` (search + add-new-with-level) for the
  opponent (singles) or partner + 2 opponents (doubles); a handicap control
  (Không / Tôi chấp / Được chấp + points). After a score is logged the opponent
  field auto-clears for quick next entry. Match list shows "vs Name (level)".
- Backend `spa()` now serves real static files from `dist` (favicon, etc.); added
  a table-tennis `favicon.svg` + `<link rel=icon>` so the browser tab shows a
  paddle instead of the default globe.
- Seeded the user's real opponent roster (20 players) into the DB.

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

The Video Analysis tab needs **Ollama running** (`ollama serve`, usually a
background service after install) with the `qwen3-vl:8b` model pulled, plus
`ffmpeg` on PATH (here at `C:\ffmpeg\bin`). All AI runs locally — no network.
