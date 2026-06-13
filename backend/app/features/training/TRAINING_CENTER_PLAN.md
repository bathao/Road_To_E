# Training Center — Design Plan

Tab 6 "Training Center" (💪). A **Tier-1 specialist coach** for off-table physical
training. It prescribes a daily session, the user ticks what they did (self-report,
trusted), and every tick is persisted as structured training-load data that (a)
auto-syncs into the Daily Tracker so the user sees it in one place and (b) is read
later by the Tier-2 **Head Coach** to make training decisions. It does *not* give the
final verdict — it produces evidence, like every other specialist.

> Status: **design only, not implemented.** Decisions below were agreed with the user.

---

## 1. Purpose & role in the two-tier brain

- **Goal of the training:** build the physical base table tennis actually needs —
  rotational core, lateral legs, low/stable centre of gravity, split-step timing,
  single-leg balance. Deliberately **no chest / biceps** (scoping choice for a short
  daily session focused on legs + core).
- **Knee-OA constraint + QUAD priority (doctor's directive).** The player has
  grade-1 knee osteoarthritis. Per the doctor, strong quadriceps offload the knee
  joint, so quad strengthening is the #1 priority and pain-free open-chain quad work
  (quad set, straight-leg raise, short-arc quad) can be done daily. The curriculum
  therefore: avoids deep squats / lunges / jumping; leads every leg day with quad
  moves; weights the cycle toward legs (3/6). Progression is reps / time-under-
  tension only — never load or impact.
- **Tier-1 contract:** persist everything in a queryable shape + expose
  `GET /api/training/report` so the Head Coach reads training-load without scraping
  UI or recomputing. The Head Coach is a *consumer*; Training Center is a *producer*.
- **Adaptive, not punitive.** After the user's reframe, the centre of gravity is
  *"what do I train today / tomorrow, sized to my level, to play better"* — a guided
  daily prescription, not a drill-sergeant punishment machine. We **trust the user's
  ticks** (no anti-cheat heuristics — they misfire and falsely accuse honest users).

---

## 2. Progression model — finite programs, sequential unlock (BetterMe-style)

Reference UI the user gave: a grid of "Day" tiles unlocked one by one, with a top
"X of N workouts" progress bar.

- Each **level = a finite program of N sessions** (default **N = 21**, ≈ 3–4 weeks at
  5/week; adjustable — 28 also fine). Three levels:
  1. `foundation` — wake up quads/glutes, learn to sit low. (default, unlocked)
  2. `explosive` — explosive strength (for looping) + core stability (don't get
     thrown off-balance on a miss).
  3. `tt_specific` — high-intensity simulation of TT movement (shadow play + ankle
     weights / resistance bands).
- **"Day" = session index within the program, NOT a calendar date.** This is the key
  decision: it decouples the program from the weekday calendar. Do Day 1 today, skip
  three days, Day 2 still waits — no broken streak, no reset, no punishment for real
  life. The calendar date a session was completed is recorded separately (`done_on`),
  and that is what the tracker reads.
- **Unlock:** completing Day N unlocks Day N+1. Completing the whole program unlocks
  the next level. **No demotion, no re-locking** — once open, it stays open (matches
  "trust the user"). If the user has been away a while, the engine may *suggest* an
  easier session, but never punishes.
- Inside a program, sessions rotate **day-types**: `legs → core → balance → legs →
  core → …`. Day-type drives which exercises appear.

**After the last level — no dead-end (coach's call).** Finishing the top level
(`tt_specific`) does NOT end the program. It enters **maintenance**: the top level
repeats in **cycles (Vòng N)** with **gentle, capped progressive overload** — each
cycle adds +2 reps / +5s holds (sets never change), plateauing after
`OVERLOAD_MAX_CYCLES` (3). Knee-safe by construction: overload is time-under-tension
/ reps only, never load or impact. The grid shows the current cycle's 21 tiles with
absolute session indices; the header shows "· Vòng N". This is the interim answer;
the **Head Coach (Tier-2) is meant to take over "what next"** with a personalised
program once it exists (it can read `/api/training/report`).

---

## 3. Data model (`backend/app/features/training/`)

New feature following the existing idiom (models / schemas / service / router / seed,
wired via the registry; tables auto-created by `create_all`; idempotent `migrate()`
for later column adds). Table prefix `tc_`.

### Static config (not in DB) — `program.py`
- **Exercise library** — one entry per exercise:
  `key`, `name_vi`, `muscle` (nhóm cơ), `tt_benefit` (why it helps table tennis —
  shown for motivation), `type` (`reps` | `timed`), `default_target`
  (e.g. `{sets:3, reps:20}` or `{sets:3, sec:45}`), `level_min`, `day_type`
  (`legs|core|balance`), `gif`, `form_cue` (form tip / warning).
  ~12–15 exercises, reused across sessions (we do NOT author N distinct GIFs):
  Sumo Squat, Lateral Lunge, Split Step, Russian Twist, Side Plank, Crunch,
  Single-leg-eyes-closed, hip/hamstring stretch, …
- **Level programs** — each level declares its N sessions; each session = a
  `day_type` + an ordered list of `(exercise_key, target)`. Generated from the
  day-type rotation + library so it stays DRY.

### DB tables
- `tc_state` (singleton): `current_level`, `unlocked_levels` (json), `level_since`.
- `tc_session`: `id`, `level`, `day_index` (1..N — the "Day" tile), `day_type`,
  `status` (`locked` | `unlocked` | `done`), `done_on` (calendar date completed,
  nullable), `completed_at`, `duration_min`, `adapted` (bool — has a video-prescribed
  exercise), `note`. Unique on (`level`, `day_index`).
- `tc_session_item`: `id`, `session_id`, `exercise_key`, `target_json` (snapshot of
  target at prescription time), `done` (bool), `done_at`, `is_prescribed` (bool —
  injected from video analysis, not part of the base program).

Sessions are materialised lazily (the program is the source of truth; a `tc_session`
row is created when its tile is first unlocked/opened).

---

## 4. Integration with Daily Tracker — option (A), "replace"

The Daily Tracker already owns a "Physical Training" checklist
(`tracker_physical_check`: date + item_key), and Overall (green/yellow), `days_physical`,
the Analysis panel, and Profile's training snapshot all read from it.

**Decision (A): Training Center becomes the place to log physical training —
effective from today (the cutover date) forward.**
- **Past days are left exactly as they are.** Existing `tracker_physical_check` data
  for days *before* the cutover stays untouched, and the Daily Tracker grid keeps
  showing (and editing, as before) those historical days the old way. We do **not**
  rewrite or remove any past physical data.
- **From the cutover date forward**, Training Center is the input surface. For those
  days the grid's Physical row becomes a **read-only mirror**: shows e.g.
  "Thể lực: ✓ 5/5 · Chân thép" with a link to Training Center; in-grid editing for
  today-onward days moves to Training Center.
- **Downstream signal is preserved unchanged.** When a `tc_session` reaches done
  (≥ 70% items ticked), the service writes the corresponding `tracker_physical_check`
  rows for `done_on` (always today-or-later). So Overall, `days_physical`, Analysis,
  and Profile keep working with **no change to their read paths** — only the *input
  surface* moved, and only for new days.
- Two axes stay cleanly separated: **day_index** = training progress; **calendar
  date** = what the tracker reads. They never conflict.
- The cutover date is stored once (in `tc_state`) so the grid knows which days are
  "legacy checklist" vs "mirror of Training Center".

### Consistency model (the user OK'd changing the DB to get this right)

We have latitude to migrate the schema for true consistency, so we avoid duplicate
writes. **One source of truth per era, the physical-day signal is derived:**
- Before cutover → `tracker_physical_check` (legacy) is the source.
- From cutover forward → `tc_session` is the **sole** source; we do **not** copy into
  `tracker_physical_check`. Instead the tracker's read paths (`days_physical`, Overall
  green/yellow, Analysis, Profile snapshot) are updated to compute the physical-day
  signal as a **union**: `(legacy checks before cutover) ∪ (done tc_sessions on/after
  cutover)`. No row is written in two places, so the two can never drift.
- This replaces the earlier write-through approach (which kept consumers untouched at
  the cost of duplicated rows). Now we touch the tracker read logic directly.
- Migrations are **additive only** (new `tc_*` tables + cutover in `tc_state`); **no
  past data is deleted or rewritten** (per the project's "never delete user data"
  rule). A one-off `scripts/migrations/` script if any backfill is ever needed.

---

## 5. Adaptive prescription — read Video Analysis directly

The "dynamic prescription" idea, decoupled from the (not-yet-built) Head Coach:
- The service calls the existing `GET /api/video/report` and inspects `va_skill`
  (`stance_posture`, `footwork`, `physical` axes — low rating / high priority) and
  accepted `va_trait` findings.
- A map (`prescription.py`) turns a weakness into a targeted exercise:
  `stance_posture` weak → Side Plank / Single-leg; `footwork` weak → Lateral Lunge /
  Split Step; etc.
- One `is_prescribed=true` exercise is injected into the currently-open session, with
  a **transparent reason** (motivating, not abusive): *"Video hôm qua cho thấy hay mất
  trụ khi giật → thêm Side Plank 45s."*
- No Head Coach dependency — `/api/video/report` is already structured. When the Head
  Coach is built, it reads `GET /api/training/report` in addition.

---

## 6. API (`/api/training`)

- `GET /today` → the currently-open session: header goal, exercise cards (target,
  GIF, tt_benefit), per-item done state, % complete, any prescribed exercise.
- `GET /program?level=` → the full day-grid for a level (tiles with status
  locked/unlocked/done) + "X / N" progress. Drives the BetterMe-style grid.
- `GET /session/{level}/{day_index}` → one session's detail.
- `POST /session/{level}/{day_index}/item/{key}` → tick/untick an item (records
  `done_at`, `done_on`).
- `POST /session/{level}/{day_index}/complete` → finalise; unlocks the next tile;
  writes the `tracker_physical_check` sync rows.
- `GET /level` → current level + unlock progress.
- `GET /report` → **Tier-1 brain view for the Head Coach**: adherence, volume by
  muscle group / day-type, current streak, level reached, recent sessions. Stable,
  machine-readable.

---

## 7. Frontend — `frontend/src/tabs/training-center/` (icon 💪)

Registered in `tabs/registry.ts`, following the other tabs' structure
(api / types / labels + components).
- **Header**: plan name + "Focus: Chân thép & trọng tâm thấp" + main goal + big
  **progress bar** + "Tiến độ: 3 / 21 buổi".
- **Day grid** (the reference layout): each tile = the session's main-exercise
  thumbnail/GIF + "Day N · Chân" + state ✅ done (dimmed + tick) / 🔓 open (bright,
  highlighted border) / 🔒 locked. Tap an open tile → session detail.
- **Session detail**: exercise cards (GIF + name + tt_benefit + target like
  "3×20" / "45s") + **Check Done** button (card dims, a "ting" sound). Prescribed
  exercises carry a "🎯 HLV chỉ định" badge with the reason.
- **Level switcher**: pick among unlocked levels; locked levels show 🔒 + the unlock
  condition ("Hoàn thành Foundation để mở").
- **Weekly summary** (coach voice, data-driven, not abusive): "Tuần này 4/5 buổi.
  Cứ thế phát huy."

---

## 8. Content task (outside code)

GIFs/images must be **bundled locally** (the project is no-network — Ollama runs
local). Put them under `frontend/public/exercises/`. ~12–15 reused clips, not 21/28
distinct ones. Implementation starts with **placeholders**; the user drops real GIFs
later. Mind repo size.

---

## 9. Build order

1. Backend feature: tables + `program.py` config + exercise library + `GET /today`,
   item tick, `complete`. Materialise + unlock logic.
2. Tracker integration: read-only mirror in the grid + write-through to
   `tracker_physical_check` on complete (keep Overall/Analysis/Profile unbroken).
3. Frontend tab: header, day grid, session detail, Check Done.
4. Level switcher + unlock progression UI.
5. `GET /report` (Head Coach contract) + adaptive prescription (read
   `/api/video/report`) + weekly summary.
6. Drop in real GIFs.

---

## 10. Open knobs (sensible defaults chosen; easy to change)

- **N sessions / level:** default **21** (28 also acceptable).
- **"Done" threshold for marking a physical day:** **≥ 70%** of items (mirrors the
  existing tracker rule).
- **GIFs:** placeholders first, real assets later.
