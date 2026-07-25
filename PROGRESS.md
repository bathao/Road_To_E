# Progress Log — Road To E (formerly "Table Tennis Coach", renamed 2026-07-25)

## Current status (2026-07-25, night) — handicap memory per opponent (committed `9629149`)

> **Resume.** Picking a singles opponent in MatchEditor now pre-fills the
> handicap from the LAST singles match against them (Tuấn Gỗ → được chấp
> 4-4-4; Lợi Phạm → 2-2-2) — user just confirms or adjusts.
>   - GET /tracker/players/{id}/last-handicap (service.last_handicap_vs:
>     newest singles playing match by date/order_index/id; doubles excluded —
>     team handicap isn't personal). Returns {found, handicap, pattern}.
>   - MatchEditor effect on [opponent, discipline]: maps the stored value
>     back onto the dropdown (uniform int → N-N-N preset, else custom
>     digits); handicap 0 → direction "Không". Suggestion only — fetch
>     failure never blocks entry.
>   - 44/44 pytest (new last_handicap_vs test), build clean. No new columns —
>     no restart strictly needed beyond the previous batch's.

## Earlier (2026-07-25, night) — per-set handicap patterns (committed `d6e7faf`)

> **Resume.** Handicap ratios are per-set sequences in real play ("chấp 202"
> = set 1: 2, set 2: 0, set 3: 2), not one fixed number. Implemented per the
> agreed design (dropdown of the 9 common ratios, no typing):
>   - **Storage:** new `tracker_match.handicap_pattern` VARCHAR (normalized
>     "2-0-2"), NULL = uniform — all 267 existing rows untouched (seed
>     add_missing_columns migration). The signed `handicap` int now stores
>     the per-set AVERAGE (rounded, min 1 so the sign survives) when a
>     pattern exists → every sign-based analytic (build_handicap_split, coach
>     bundle, future ELO scalar) keeps working unchanged.
>     `service.normalize_handicap_pattern` collapses uniform ("222") and
>     empty input to None; uniform ratios still store as plain ints.
>   - **MatchEditor:** stepper replaced by a dropdown — presets 0-2-0, 2-0-2,
>     2-2-2, 2-3-2, 3-2-3, 3-3-3, 3-4-3, 4-3-4, 4-4-4 (default 2-2-2) +
>     "Khác…" free-digit input (digits only, e.g. "42024") for exceptions.
>     Direction seg (Không / Tôi chấp / Được chấp) unchanged.
>   - **Display:** MatchEditor list + Match Stats h2h lines show the sequence
>     ("chấp 2-0-2") for patterned matches, the plain number otherwise.
>   - 43/43 pytest (new normalize test), build clean. Restart start.bat
>     (new column via seed).

## Earlier (2026-07-25, end of day) — Tournaments + rename (committed `9e93606`)

> **Built & verified:** 42/42 pytest, tsc + vite build clean, coach-bundle
> render smoke-tested. User has real data in already (3+ tournaments). Restart
> start.bat once (new table tournament_entry_member + new APP_TITLE).
> Same-day iterations after the base feature (all in this batch):
>   - **Strip v2:** shows up to 3 nearest upcoming (one line each, per-row
>     urgent color); "+N more" button (stopPropagation) expands to ALL
>     upcoming, "Show less" collapses. English labels by user request.
>   - **PlayerPicker bugfix (pre-existing, exposed by the team picker):**
>     after a pick the input keeps focus, so onFocus never re-fires and the
>     dropdown stayed closed while typing — the "+ Thêm" button could never
>     appear. Fix: setOpen(true) in the input's onChange. Benefits
>     MatchEditor too.
>   - **App renamed "Road To E"** (was "Table Tennis Coach"): AppShell header
>     (🏓 kept), index.html title, APP_TITLE, package.json/lock
>     (road-to-e-frontend), README/start.bat/PROGRESS headers.
> Implementation notes:
>   - `level_limit` (tournament-level rank limit) added same day on request —
>     amber "Trình: …" chip on card + strip, shown to the coach, migrated via
>     seed add_missing_columns (table may pre-exist). v2 same day: input is a
>     TOGGLE ROW of the fixed ladder A..I + an explicit "Open" button (user is
>     rank G; tournaments look like "D E F"/"E F G"/"G H"/Open). Stored
>     unchanged as a string ("E F G" normalized A→I, or "Open", or null =
>     unspecified). The per-entry free-text `division` input was REMOVED from
>     the form (redundant with the tournament-level limit; column + display
>     of old values kept).
>   - Team entries v2 (same day): roster picked from the shared player pool
>     via PlayerPicker (add-new inline works) — new table
>     `tournament_entry_member` (entry_id, player_id; created by create_all,
>     needs a start.bat restart), EntryIn.teammate_ids / EntryOut
>     .teammate_names; `team_members` text now means optional team name.
>     Card/strip/coach labels combine both ("Đồng đội — CLB X · Nam, Bình").
>   - Backend `app/features/tournament/` (models/schemas/service/router/seed,
>     registered in registry.py). API: GET/POST /api/tournaments,
>     PUT/DELETE /api/tournaments/{id} — every mutation returns the fresh
>     full list (deliberately NOT 204: a 204 body reads as `undefined` in the
>     FE client, which is useMutate's failure sentinel — the audit's
>     deleteMatch lesson).
>   - `upcoming_for_coach(db, horizon_days=90)` feeds the bundle section
>     "GIẢI ĐẤU SẮP TỚI" (+ SYSTEM_PROMPT rule: week plan MUST aim at the
>     nearest tournament, right discipline/partner, taper before match day).
>   - FE: `components/tournaments/` (helpers + TournamentStrip +
>     TournamentSection). index.tsx holds ONE useLoad shared by both; strip
>     click anchor-scrolls to the section. Countdown is local-calendar
>     (fromIso), "HÔM NAY"/"ĐANG DIỄN RA" for day-0/multi-day-running.
>     Strip horizon 45d, urgent (<=7d) turns red. Form collapsed by default;
>     past capped at 3 with toggle. Partner picked via existing PlayerPicker
>     (kept as {id,name} pill when prefilled from an entry).
>
> **Approved design (2026-07-25, after two rounds of debate):** tournaments
> are a *scheduling commitment*, NOT a results store — match results keep
> flowing into the Daily Tracker as usual (user never logs team-event
> matches). Purpose: the user pins "on day X I play discipline Y" and the
> Head Coach plans training toward it.
>   - NO new tab, NO modal. Daily Tracker hosts both pieces:
>     * **Strip** (one line, under the toolbar, ABOVE the grid): nearest
>       upcoming tournament within 45 days — "🏆 name · còn N ngày · chips";
>       click = anchor-scroll to the section. Hidden when nothing upcoming.
>     * **`<TournamentSection />` at the very bottom** (below AnalysisPanel —
>       ordered by usage frequency): upcoming cards with countdown +
>       entry chips, add-form COLLAPSED behind "＋ Thêm giải", past
>       tournaments capped at 3 with a toggle.
>   - Backend: new feature `tournament/` — `Tournament` (name, location,
>     start/end date, note) + `TournamentEntry` (discipline singles|doubles|
>     team, partner_id FK tracker_player for doubles, team_members free text
>     for team, division text). NO result fields (cut deliberately).
>   - Head Coach bundle gains "GIẢI ĐẤU SẮP TỚI" (name, days left, entries,
>     partner) — the actual point of the feature.
>   - Graduation rule: if tournament history/results/analytics is ever
>     wanted, THAT is when this becomes its own tab.

## Earlier (2026-07-24, night) — wave 1 done (`2476c1d`); NEXT after tournaments: ELO rating

> **Resume here tomorrow (2026-07-25).** Everything committed (`2476c1d` code
> + `2cefbc8` PROGRESS), tree clean, 40/40 pytest, build clean. Restart
> start.bat once so the first DB backup runs.
>
> **Next up — roadmap wave 2: ELO-with-handicap rating** (agreed 2026-07-24):
>   - One rating per player (me + every opponent), updated per match in date
>     order; the signed `tracker_match.handicap` (+N = I give N points/set)
>     folds into the expected score, so handicapped matches move ratings less
>     when the result matches the rebalance. Levels (below/equal/above) stay
>     as the user's static labels; rating is the objective view next to them.
>   - GUI: rating trend line on Match Stats + Profile; feed rating trend into
>     the Head Coach bundle ("lên trình" gets real math instead of raw
>     win-rate, which is biased by how often he plays up).
>   - Full roadmap (waves 3-5): weekly auto-verdict + tournament goals →
>     set scores + mobile quick-log → opponent dossiers + tech-debt items
>     listed in the audit entry below.
>
> **Wave 1 (this batch, committed `2476c1d`):**
>   - **Daily DB auto-backup** (`app/core/backup.py`): every server start
>     snapshots tabletennis.db → `backend/data/backups/<name>-YYYY-MM-DD.db`
>     (once/day, keeps 30, WAL-safe via sqlite3 backup API, never blocks
>     startup). Runs FIRST in lifespan — before init_db/seeds — so a bad
>     migration can't taint the snapshot. backups/ is gitignored. Gotcha
>     found by test: sqlite3's `with` is a transaction context, NOT a closer —
>     connections must be closed explicitly or Windows keeps the file locked
>     (WinError 32 on prune). Smoke-tested on the real DB (0.34 MB snapshot).
>   - **Coach Package renew button**: when the card shows status `over`, a
>     "★ Bắt đầu gói mới từ buổi 11" button appears; POST
>     /tracker/coach-packages/start-next flags the over-run block's 11th
>     session as the new package's start (always session size+1, so sessions
>     12+ land in the NEW package). 400 when the block isn't over yet.
>     Backend service + endpoint + FE card wiring (AnalysisPanel local busy/
>     error states).
>   - Note: pytest's tmp_path fixture is broken on this machine (Temp\
>     pytest-of-MSI has denied ACLs; undeletable) — test_backup.py uses its
>     own tempfile fixture instead.
>   - **Verified:** 40/40 pytest (3 new), build + tsc clean.

## Earlier 2026-07-24 (evening) — project-wide audit batch (committed `490fe63`)

> **Resume.** Full-project review (4 parallel review agents, every finding
> re-verified against the code before touching it), then fixes applied.
> 37/37 pytest (1 new test), `npm run build` clean. Committed as `490fe63`;
> nothing in flight after it.
>
> **Bugs fixed — backend:**
> - head_coach: crash/restart mid-LLM-call left `pending` chat / `generating`
>   verdict rows forever → chat input + Generate button bricked (409, no job
>   alive). New `recover_stuck_jobs()` runs from seed at startup, flips them
>   to visible errors (+ regression test).
> - head_coach: `run_generate_job` persisted OUTSIDE its try (a commit failure
>   stranded the row in `generating`); moved inside + one retry on empty
>   verdict (same first-call-after-load quirk as chat) + non-dict guard (both
>   jobs). `PlanDay` fields got defaults so a stored plan item missing
>   `detail` can't 500 GET /assessment permanently.
> - training: `_materialise` SELECT-then-INSERT race (coach background jobs
>   read training data on their own session) → IntegrityError caught,
>   winner's row re-fetched.
> - tracker: `order_index` now max+1 (was count() → duplicates after
>   delete/move); explicit `order_index=0` no longer treated as unset
>   (schema default None); match-stats ordering ties broken by order_index so
>   `last_result` is right on multi-match days; coach-package status computed
>   for EVERY package (history said "ok" for overrun blocks); upsert-activity
>   collapses legacy duplicate rows (pre-unique-index DBs) and drops ★ on
>   0-minute rows (star was visible in grid but invisible to package math);
>   xlsx/csv export now includes the cell note + ★ like the on-screen grid;
>   ActivityOut unconstrained (one legacy out-of-range row must not 500
>   /weeks).
>
> **Bugs fixed — frontend:**
> - daily-tracker: deleting a match never refreshed the UI (DELETE→204→
>   undefined == run()'s failure sentinel); AnalysisPanel out-of-order
>   response race (seq guard); PlayerPicker add/toggle-pips swallowed errors
>   into unhandled rejections (now caught + shown) + stale search-result
>   guard; DurationEditor Save disabled on blank input (blank saved 0 =
>   silent delete).
> - head-coach: one transient status-poll failure ended polling with a false
>   "Phân tích thất bại" (now only a *returned* error status is terminal);
>   notebook add/delete errors were invisible and the typed note was lost
>   (error shown, input cleared only on success); chat history load error
>   showed as fake empty state; DevLogs autoscroll no longer yanks you down
>   every 3s while reading scrollback.
> - profile: error banner never cleared after recovery + range-switch race
>   (alive guard); match-stats: empty-state text no longer flashes during
>   first load; WorkoutPlayer: ExerciseImage keyed by gif (fallback no longer
>   sticks across consecutive steps) + NaN progress guard; LineChart guards
>   empty points.
> - Dead code removed: videoApi.updateTrait, DAY_LABEL, Bar.title/highlight,
>   LEVELS re-export shim (MatchEditor imports shared/levels directly),
>   DIRECTIVE_AREAS/DIRECTIVE_METRICS duplicate constants, redundant
>   `editing &&`.
>
> **Known findings deliberately NOT fixed (candidates, in rough priority):**
> - Retired paste-analysis pipeline still alive in backend (video router
>   /reports* + /health/model endpoints, service create/parse/list/delete
>   report, text_synth.extract_findings) — delete when convenient. Also
>   `prescription_for` still injects exercises from the RETIRED va_skill
>   ratings into every new training session — product decision needed
>   (contradicts the "no model guesswork" head-coach principle).
> - FE `tabs/video-analysis/` folder is the Profile tab's engine, misnamed —
>   move under tabs/profile/ someday. Profile tab still hand-rolls fetch
>   state (port to useLoad would also fix editors closing on failed saves);
>   a shared usePoll hook would unify 3 polling loops.
> - SQLite FK pragma still OFF (dangling ids accepted silently);
>   start_chat double-send race (mostly neutralized by startup recovery);
>   build_week vs _build_grid ~70-line duplication (they drift — the export
>   parity bug came from exactly this); legacy physical-checks writes allowed
>   post-cutover; DELETE /tracker/activities/{id} endpoint unused by FE.
> Restart start.bat to load the new backend.

## Earlier 2026-07-24 — all committed, no work in flight

> Working tree clean; latest commits `609e648` (handicap-aware Head Coach,
> below) + `e341cea` (PROGRESS). Today's only event was DATA, not code: the
> user renewed the coaching package after session 10 and marked session 11
> with the existing ★ "Start of a new 10-session package" checkbox (open the
> Train-with-Coach cell of that day in the grid; enabled only on session 1 or
> 11+ via /coach-package-start-allowed). Known UX gap / next candidate: the
> Coach Package card only ASKS "mark the new package's start?" — no action
> button; a one-click "start new package from session 11 (date X)" button on
> the card was offered and the user may want it at the next renewal (~2
> months). Other next candidates remain under "Status (2026-07-12, end of
> day)" → Next candidates.

## 2026-07-23 — handicap-aware Head Coach (committed `609e648`)

> **Resume.** Head Coach now sees and reasons about HANDICAP (tỉ lệ chấp) —
> user request: a handicapped match must be read differently from an even one.
> Committed as `609e648`; nothing in flight after it.
>   - **New fact block:** `tracker_service.build_handicap_split(db, from, to)`
>     — win rates by opponent level × handicap direction (even / receive /
>     give; signed `tracker_match.handicap`, +N = give, −N = receive), named
>     opponents, same MATCH_STATS_FLOOR clamp; empty cells omitted. Injected
>     into the bundle as `match_detail.by_level_handicap` and rendered as a
>     "Tách theo CHẤP" section right under the by-level lines (gets the
>     [MẪU NHỎ] tag per cell too). No API/GUI change (match_detail is a dict;
>     the FE type has an index signature).
>   - **Prompt rules (both SYSTEM_PROMPT + CHAT_SYSTEM_PROMPT):** never pool
>     handicapped with even matches; receiving points vs above-level = the
>     match was pre-balanced (winning ≠ caught up — real yardstick is even
>     play); giving points to below-level = self-imposed disadvantage (losing
>     more than even play is expected, not regression). "tỉ lệ chấp" added to
>     the source list in the persona intro.
>   - **Verified:** 36/36 pytest (new `test_build_handicap_split_directions`);
>     real-DB render shows e.g. above-level: even 6/25 (24%) vs được chấp
>     0/13 (0%) — exactly the split the coach needed. Restart start.bat to
>     load the new backend, then "Phân tích lại" for a fresh verdict.
> Before this: everything committed (latest `19c38fc`, 2026-07-13 — chat +
> notebook batch). Next candidates remain the ones under "Status (2026-07-12,
> end of day)" → Next candidates, minus what's already done (A/B → qwen3.5:9b;
> Phase-3 lite done; small-sample guard done).

## 2026-07-13, evening — Coach chat + notebook (committed `19c38fc`)

> **Resume.** New feature (user-requested): interact with
> the Head Coach for short-term, specific goals (e.g. "đánh đơn tốt cho giải
> 2/8") instead of only weekly verdicts.
>   - **Chat ("Trao đổi với HLV"):** `hc_chat_message` table keeps every turn
>     forever — the conversation IS the coach's verbatim memory. Each reply is
>     grounded server-side: live facts bundle + notebook + full history from
>     the DB (`_CHAT_HISTORY_CHAR_BUDGET=8000` chars per call; DB keeps all).
>     Same background-job pattern as the verdict: POST /api/head-coach/chat →
>     pending coach row → poll GET /chat until `pending` clears. One question
>     at a time (409 while a reply is in flight). CHAT_SYSTEM_PROMPT +
>     CHAT_RESPONSE_SCHEMA {reply, new_notes} in prompt.py; temperature 0.4.
>   - **Notebook ("Sổ tay HLV"):** `hc_note` table. The model AUTO-writes
>     durable facts (goals/deadlines/constraints/agreements) after each reply
>     — user's explicit choice, no confirmation step. Guardrails: ≤3
>     notes/reply, ≤300 chars, case-insensitive dedup, blanks skipped. Player
>     can add (`POST /notes`) and delete (`DELETE /notes/{id}`) by hand.
>     Notebook is injected into every chat reply AND the weekly verdict
>     (gather_bundle → coach_notes → "=== SỔ TAY HLV ===" section), so both
>     stay aligned.
>   - **Empty-reply retry:** first structured-output call right after model
>     load can return "" (seen in smoke test turn 1) — run_chat_job retries
>     once before marking error. `run_chat_job(db_or_none)` accepts a session
>     for tests/scripts; defaults to SessionLocal.
>   - **Frontend:** chat bubbles + polling + auto-scroll (CoachChat.tsx),
>     notebook panel with add/delete (CoachNotes.tsx), section always visible
>     (even before the first verdict); fmtTime moved to fmt.ts. hc-interact
>     grid CSS in head-coach.css.
>   - **Verified:** 34/34 pytest (8 new chat/notes tests), build clean, 3-turn
>     smoke with real qwen3.5:9b on a **DB copy** (real DB untouched — the
>     example goal "giải 2/8" must not pollute the real notebook): turn 2/3
>     perfect, auto-notes correct, turn-3 recall exact.
>   - New tables are created by Base.metadata.create_all at startup — restart
>     start.bat, then just chat in tab Coach.
>   - **Same-evening follow-ups (user feedback):** (1) Coach tab redesigned to
>     full-width two-column — verdict left, sticky chat+notebook right
>     (collapses <1100px); (2) pronoun rule in BOTH prompts: coach is younger
>     → always "anh"/"tôi", never "em/cậu/bạn" (smoke-verified); (3) metric
>     definitions injected into the verdict prompt so order wording matches
>     what the app measures + METRIC_SCOPE hints next to progress bars ("tổng
>     cầm vợt: tập + thi đấu"); (4) dev log panel "🛠️ Log kỹ thuật" (collapsed
>     details at the bottom of the verdict column): GET /head-coach/debug
>     returns an in-RAM ring buffer of the last ~400 backend log lines
>     (core/logbuffer.py, installed in main.py) + Ollama /api/ps VRAM
>     occupancy — for diagnosing OOM/fallback/slow generations; polls 3s only
>     while open. (5) User constraints recorded in the real notebook via API:
>     coach time hard-capped at 2-3h/week (budget+time; extra hours go to
>     partner), and he wants ~20 matches/week (4/week felt way too low).
>     35/35 tests, build clean.

## Earlier today (2026-07-13)

> **Resume (2026-07-13, latest).** Finished yesterday's three follow-ups:
>   - **Model A/B (real bundle, 3 rounds):** compared qwen3:14b vs gpt-oss:20b
>     vs qwen3.5:9b on the live coach bundle. Winner **qwen3.5:9b** — best
>     Vietnamese, best number-grounding (14b hallucinated units: "4570 phút =
>     51h/tuần"; gpt-oss mixed English + empty orders), correctly applies the
>     small-sample rule and uses day notes. `HEAD_COACH_MODEL = "qwen3.5:9b"`
>     (settings.py, rationale in comment); `resolve_model()` falls back to
>     TEXT_MODEL with a log warning if the configured model isn't pulled.
>     Decision: did NOT pull qwen3:30b-a3b (18GB) — better options were already
>     local. A/B artifacts in the session scratchpad (ab_results*.json).
>   - **Small-sample guard:** win-rate segments with <5 matches are tagged
>     `[MẪU NHỎ]` in the context block (`MIN_SAMPLE_MATCHES`, service._wr) and
>     the prompt forbids concluding from them (h2h person-records exempt).
>   - **Phase-3 lite (directives → trackable commitments):** Directive gained
>     `metric` (enum of 7 weekly metrics) + `value`; the model must fill them
>     (required in RESPONSE_SCHEMA; ""+0 when not quantifiable; service
>     `_sanitize_directives` drops implausible values by range). New
>     `GET /api/head-coach/directive-progress` computes THIS WEEK's actual from
>     the DB (TC sessions, racket hours, coach hours, matches by kind) vs each
>     target; the Coach tab renders a progress bar per trackable directive
>     ("Tuần này: 2/4 buổi", green ✓ at 100%). Deliberately NOT auto-injecting
>     model-chosen exercises into Training Center — targets are tracked, the
>     knee-safe program stays code-owned. 2 new tests (26 total), build clean.
>   - Committed as `10830c7` (together with yesterday's batch), after one more
>     A/B round: gemma4:12b tested on the real bundle and rejected (Vietnamese
>     typos everywhere, 450min-vs-12.5h unit mismatch, self-contradicting week
>     plan volume, slower) — qwen3.5:9b stays.

## Status (2026-07-12, end of day)

> **Where things stand / pick up tomorrow:**
>   - App is now 5 tabs: Daily Tracker · Coach · Match Stats · Profile ·
>     Training Center. Đã bỏ "Phân tích kỹ thuật" + "Tactical Playbook" (chi
>     tiết ở resume "2026-07-12 b" bên dưới); Head Coach v2 chỉ phân tích sự
>     thật trong database.
>   - **Commit state:** the hardening pass IS committed (`4449539`); the rest
>     of this batch (Racket Time, 2-tab retirement + Head Coach v2, tactics
>     removal, VN-timezone fix) was committed on 2026-07-13 as `10830c7`.
>   - **User must restart `start.bat`** — the server that's running still has
>     the pre-refactor backend; frontend dist is already rebuilt.
>   - **Next candidates (discussed, not started):** (1) A/B thử
>     `HEAD_COACH_MODEL = "qwen3:30b-a3b"` (MoE, chất lượng hơn 14b, chạy nền
>     nên chậm chút không sao — knob riêng đã có trong settings.py); (2) Phase 3
>     write-back: directives của Coach → bài tập thật trong Training Center;
>     (3) cân nhắc ngưỡng mẫu tối thiểu (ít trận thì đừng kết luận win-rate).

> **Resume (2026-07-12 b).** **Retired 2 tabs + Head Coach v2
> (database-facts only)** — user decision: model-parsed technique commentary is
> not trustworthy, so the coach must reason over recorded results only.
>   - **Tabs removed from the UI:** "Phân tích kỹ thuật" (video-analysis paste
>     flow: index/PasteForm/ReportList/ReviewPanel deleted; ProfilePanel/
>     SkillBoard/TraitBoard + api/types/labels KEPT — the Profile tab uses them,
>     manual findings still work) and "Tactical Playbook" (frontend folder +
>     backend feature folder deleted, router unregistered). **DB untouched:**
>     `playbook_tactic` (0 rows — nothing was ever saved) + all `va_*` tables
>     and rows remain (never delete user data); backend /api/video/* stays for
>     the Profile tab.
>   - **Head Coach v2 bundle** (`gather_bundle` rewritten): tracker volume +
>     racket time, match aggregates, **match detail** (win-rate by opponent
>     level, TRẬN TẬP vs TRẬN GIẢI, monthly trend, top-8 head-to-head via 3×
>     `build_match_stats` calls over 180d), Training Center report, and the 12
>     most recent **day notes** (human signal). No video/tactics sources.
>     `SourceSummary` keeps legacy `video`/`tactics` fields so old snapshots
>     still parse/render.
>   - **Prompt rewritten** (prompt.py): sources = database facts; judge progress
>     via trends (win-rate by month / by opponent level), practice-vs-official
>     gap, problem opponents (h2h), vs-pips, volume (racket time); use day notes
>     as context; **forbidden to invent stroke-technique observations** it
>     cannot see; thin-data honesty + knee-safety kept. Player name now comes
>     from the (editable) profile.
>   - Verified on the real DB: bundle renders ~2.8k chars of pure facts (e.g.
>     22% vs trên-cơ, TẬP 47% vs GIẢI 30%, July slump 15%) — exactly the
>     patterns the coach should push on. 24/24 pytest, `npm run build` clean
>     (bundle −18KB JS / −5KB CSS), OpenAPI types regenerated.
>   - HEAD_COACH_PLAN.md updated (sources table). Old assessments (4 rows) keep
>     rendering via legacy fields.
>   - **Follow-up (same session):** dropped the "Chiến thuật áp dụng trong
>     trận" section from the verdict entirely (user: the model can't know what
>     tactics he actually plays) — removed from RESPONSE_SCHEMA, prompt,
>     DIRECTIVE_AREAS, the UI section + its CSS; `TacticSuggestion`/`tactics`
>     kept as legacy so old snapshots parse. Also **fixed the verdict
>     timestamp**: created_at is stored naive-UTC → API now re-attaches UTC
>     (`Z` suffix) and `fmtTime` renders in Asia/Ho_Chi_Minh (was showing 7h
>     early, e.g. 16:09 instead of 23:09).

> **Resume (2026-07-12).** **Project-wide hardening pass** (from a full
> code review): safety, bugs, performance, tests. Committed as `4449539`.
> Highlights:
>   - **Data safety:** `tracker/seed.seed_categories` no longer deletes
>     categories/activities/matches missing from the defaults — it keeps them and
>     logs a warning (never delete user data). Unique index on
>     `tracker_activity(date, category_id)` added non-destructively (skipped with
>     a warning if legacy duplicates exist). SQLite now runs WAL +
>     `busy_timeout=5000` (`core/db.py`).
>   - **Real bug fixes (frontend):** Profile tab dùng UTC (`toISOString`) — trước
>     7h sáng VN "hôm nay" bị tính là hôm qua → fixed via shared local-date
>     helpers; ReviewPanel drafts được merge thay vì reset mỗi 2.5s poll (hết mất
>     chữ đang gõ); WorkoutPlayer countdown side-effects moved out of the state
>     updater (StrictMode-safe).
>   - **Silent failures eliminated:** new `shared/useApi.ts` (`useLoad` with
>     stale-response guard + `useMutate`) adopted across all tabs — every write
>     now surfaces errors in the UI; backend got `logging` throughout (the
>     swallowed `regenerate_skills` failure now logs + rolls back).
>   - **Head Coach generate chạy nền** (mirrors parse_report): `hc_assessment`
>     gets `status`/`error_msg` columns (idempotent seed migrate), POST /generate
>     returns ngay, GUI polls GET /status rồi refetch — hết request treo 10 phút.
>   - **Perf:** `selectinload` + 365-day floor on training `report()` /
>     `physical_day_map()` (N+1 gone from every tracker load); `/assets/*` served
>     `immutable` (only index.html stays no-store).
>   - **LLM prompts:** trait caps (150 profile / 20 per aspect) + `num_ctx=16384`
>     so Ollama never silently truncates; player name read from `profile.name`
>     (hết hardcode); docstrings về review-gate đã sửa cho đúng auto-accept design.
>   - **Validation:** Pydantic `Literal`/bounds cho MatchIn (discipline, best_of
>     3|5|7, sets 0..4), duration ≤ 24h, player name không rỗng; training
>     complete/substitute từ chối level/exercise không hợp lệ; unknown `/api/*`
>     trả 404 thay vì index.html; DELETE report trả 404 khi không có.
>   - **Dedup:** `core/sqlite_migrate.py` (một `add_missing_columns` thay 3 bản
>     copy), một `ASPECT_LABEL_VI`/`SETTING_LABEL_VI` (video schemas) dùng chung
>     với Head Coach, một `PHYSICAL_YELLOW_RATIO`, một `_result_letter`; FE:
>     `SKILL_STATUS_CLASS` dùng chung, date helpers gom về `shared/dates.ts`,
>     BarChart chết đã xóa (type `Bar` chuyển sang LineChart).
>   - **styles.css tách theo tab:** `src/styles/{base,daily-tracker,…}.css` (8
>     file, `styles.css` chỉ còn @import) + **~610 dòng CSS chết đã xóa**
>     (upload/lightbox/annotator/gate/progress cũ, `minutes-*`) — grep-verified.
>   - **Tests:** `backend/tests/` — **22 pytest** (in-memory SQLite, không đụng
>     DB thật): coach-package math, overall colors, match-stats grouping,
>     activity upsert, seed safety, autoregulation clamp, maintenance-cycle math…
>     `requirements-dev.txt` mới. Chạy: `.venv\Scripts\python -m pytest tests -q`.
>   - **OpenAPI typegen:** `npm run gen:api` → dump schema qua
>     `backend/scripts/dump_openapi.py` → `src/shared/api/schema.d.ts`
>     (openapi-typescript) để soát drift giữa types.ts viết tay và Pydantic.
>   - Verified: backend boots on the real DB (idempotent migrations applied:
>     `hc_assessment.status/error_msg`, activity unique index), 22/22 tests pass,
>     `npm run build` clean, smoke-tested weeks/report/status/assets endpoints.
>     **Lưu ý:** server đang chạy (start.bat) vẫn là code cũ — cần khởi động lại
>     để backend mới có hiệu lực.

> **Resume (2026-06-27).** Training Center got **4 new seated weighted-abs
> exercises** + the whole pose library was **animated**. Two parts, all committed
> this session:
>   - **4 new "bụng-có-tạ" (ngồi) moves** sourced from a FitwithCarla reel the user
>     shared (frame-by-frame): `db_seated_leg_press` (nâng đùi luân phiên + đẩy tạ
>     ra trước), `db_seated_overhead_tuck` (đẩy tạ qua đầu + co gối), `db_seated_leg_spread`
>     (giữ tạ qua đầu, giang chân ra–vào), `db_seated_pass_under` (nâng đùi, luồn
>     tạ dưới đùi). All compound (bụng/core + đùi/gập-hông + tay/vai) and **knee-safe**
>     (seated, no knee load/flexion/jump). Added to the **1kg-dumbbell pool**
>     (`DUMBBELL_KEYS` 6→10, interleaved; rotation now covers all in ~5 days), each
>     with muscle/tt-benefit/form-cue + 4-step `HOW_TO`. Source used 2kg; kept 1kg to
>     match the existing daily pool (target ramps weekly anyway). Only `program.py`
>     + `constants.ts` (POSE map) touched.
>   - **Exercise illustrations are now ANIMATED.** The 22 static stick-figure pose
>     SVGs (`frontend/public/exercises/poses/*.svg`) + the 4 new ones = **26 hand-
>     authored animated SVGs** (SMIL `<animate>`/`<animateTransform>`), each acting
>     out the rep (leg lift, press, twist, spread, hinge…). Runs in the existing
>     `<img>` loader (declarative SVG animation plays in `<img>`); GIF at
>     `/exercises/<key>.gif` still wins if present. Then **upgraded the figure style**
>     per the user: thicker "mass" torso (12px), fuller limbs (6.5–7px), head+neck,
>     the **active muscle highlighted blue**, weights in red — reads as a body, not a
>     stick. No code change (same filenames); `npm run build` clean; ~0.6KB/file.
>   - **Honest limit:** can't generate real-person GIFs locally (no image/video gen);
>     web GIFs are copyright-risky and rarely match these niche moves — so the
>     animated SVG is the self-made, no-copyright solution. User confirmed it renders
>     in-app and approved the fuller-body restyle.

> **Resume (2026-06-26).** Redesigned the **Daily Tracker
> Analysis comparison chart** into a single composite view + a grid-aligned axis.
> All frontend, `npm run build` clean, **committed this session** (2026-06-27).
>   - **One composite chart, all three metrics** — replaced the 1-series chart +
>     `Training time / Matches / Physical days` toggle with a new
>     `shared/ui/ActivityChart.tsx` that draws each metric in the form that fits
>     it on a shared time axis: **training time = filled area+line** (left "hours"
>     axis), **matches = line+dots** (right "count" axis overlay), **physical
>     days = a strip of squares** below the plot. One hover band shows all three
>     for that day. `LineChart` left untouched (Match Stats still uses it).
>   - **Day axis aligned to the grid above** — the user's key ask. `WeekGrid`
>     measures its "Category" column width (`ResizeObserver` + `useLayoutEffect`)
>     and reports it up (`onLayout`); `DailyTracker` → `AnalysisPanel` →
>     `ActivityChart` use it as a left gutter, with each day centred in an equal
>     slot (same model as the grid's `table-layout:fixed` columns) and **zero
>     horizontal padding** on the chart card, so a chart point sits directly under
>     its grid day column. Only active in per-day mode (Week/Month/short Custom);
>     degrades when the grid is wide enough to scroll horizontally.
>   - **Reordered + trimmed** — comparison chart now leads the Analysis section
>     (right under the grid for side-by-side reading); summary cards moved below;
>     the "Training time by category" bars block was **deleted** (its `minutes-*`
>     CSS kept — Profile tab still uses it).
>   - **Harmonised** — title + legend moved **inside** the chart card (one
>     cohesive widget, no more legend stranded at the far right); summary cards
>     `auto-fill` → `auto-fit` so they fill the full width; dead CSS removed
>     (`comparison-head/-title`, `metric-seg`).
>   - **Colours echo the grid semantics** — training = **green** (`#5fa83c`, the
>     green training rows), matches = **blue** (`--accent`), physical = **yellow/
>     gold** (`#e0a800`, the yellow Physical row). Applied across line/area/dots/
>     hover/legend/tooltip swatches/strip/right-axis.
>   - **Files:** new `ActivityChart.tsx`; edited `AnalysisPanel.tsx`,
>     `WeekGrid.tsx`, daily-tracker `index.tsx`, `styles.css`.

> **Resume (2026-06-17).** Training Center got **daily-staple exercises**
> the player now does **every session**, each on its own progressive ramp,
> independent of the level/day-type rotation (`90f3517`):
>   - **Fixed daily staples:** `gyro_ball` (powerball, per hand, timed) +
>     `thigh_lift_bottle` (supine hip/core lift with a bottle/1kg, per side).
>   - **1kg-dumbbell pool (6 moves)** rotated `DUMBBELL_PER_DAY` (2) per day on a
>     3-day cycle, interleaving core/rotation + shoulder/back so the daily load
>     varies.
>   - **`daily_target()`** ramps reps/seconds ~weekly (capped) off a monotonic
>     `global_day_number` and respects the pain/RPE autoregulation bias; knee-safe
>     (sets fixed, seated/standing or hip-hinge, no added knee load).
>   - **`service._ensure_daily`** appends them to the open session idempotently
>     (mirrors `_apply_prescription`), so an already-open session picks them up.
>   - Frontend pose-SVG fallbacks mapped for the new exercise keys.
>   - Touches only `program.py` (+190), `service.py` (+34), `constants.ts` (+8).

> **Resume (2026-06-15).** Big pivot on the "Video Analysis" coach +
> several UX commits. **Headline: the entire local CV/VLM video pipeline was
> ripped out and replaced with a text intake** (`6c4d569`). The local VLM proved
> ineffective, so the tab no longer touches video at all:
>   - **Removed all CV:** `analyzer.py` (VLM, 1721 lines), `ball.py`,
>     `identity.py` (the ArcFace/body-reID engine from the *previous* resume note
>     below — now gone), `table_roi.py`, pose/metrics, the clip
>     upload/detect/confirm flow + image gallery. Trimmed the heavy deps
>     (opencv/mediapipe/ultralytics/insightface/onnxruntime) from requirements.
>     `ANALYSIS_UPGRADE_PLAN.md` deleted; new `TEXT_ANALYSIS_PLAN.md` is the design.
>   - **New flow:** paste an analysis produced **elsewhere** (e.g. a cloud model),
>     tagged with the **date** it pertains to + the **setting (practice vs match)**.
>     `text_synth.extract_findings` parses it on the shared local text model
>     (`qwen3:14b`, same as the Coach); findings **auto-accept** (the user curated
>     the text — no review gate) and the skill ledger auto-rebuilds.
>   - **Full practice/match separation:** `va_skill` is now keyed on
>     `(aspect, setting)`; `va_skill_snapshot` carries setting + `analysis_date`,
>     giving a rating/finding **history over time** (replaces the old pose
>     metric_trends as the progress signal). `build_report` exposes per-setting
>     skills/history + a practice-vs-match contrast; the Head Coach reads the
>     per-setting gap and is prompted to prescribe match-specific fixes.
>   - **DB migration additive:** drops the dead video tables, rebuilds `va_skill`
>     for the composite key; profile basics preserved.
>   - **UI split:** the "Phân tích kỹ thuật" tab (📝) is now pure intake
>     (PasteForm + ReportList + ReviewPanel); the **living profile** (editable
>     basics, AI summary, skill radar+bars, per-setting SkillBoard, findings
>     TraitBoard) moved to the **Profile** tab.
>   - **Open:** parsing/synthesis only exercised with **stubs** — the live Ollama
>     calls still need a real-model sanity check.
>
> **Other 2026-06-15 commits:**
>   - **Tabs reorder/rename** (`1f5697c`): Daily Tracker is now first = the default
>     tab; "Head Coach" label → **"Coach"**; "Video Analysis" → **"Phân tích kỹ
>     thuật"** (📝). Tab ids unchanged.
>   - **Training Center backdated logging** (`93c0f0f`): the complete-session
>     feedback modal gets a date picker (Hôm nay / Hôm qua / lịch, max = today);
>     API/service accept optional `done_on` (clamped, never future).
>   - **Daily Tracker chart trim** (`f6c8a22`): comparison chart is **line-only**
>     now (dropped the Columns view); metric selector limited to
>     time/matches/physical (removed Wins, Win rate, Days trained). Summary cards
>     unchanged.
>
> ⚠️ The resume notes and Tab-4 descriptions BELOW this line describe the
> **old CV/VLM pipeline that no longer exists** — kept for history only.

> **Resume (2026-06-14, latest) [SUPERSEDED — this CV identity engine was removed in `6c4d569`].** Fixed the long-standing **player-identity**
> problem ("which one is Thảo") in Video Analysis — the old VLM-guess approach was
> unreliable, forcing a hand-drawn box on every clip. New embedding-based engine
> `video_analysis/identity.py`:
>   - **Face (primary):** InsightFace (RetinaFace + ArcFace `buffalo_l`, 512-d, CPU
>     via onnxruntime). **Body re-ID (fallback):** torchvision ResNet-50 appearance
>     embedding (for frames with no clear face). Models download once, then offline.
>   - **Enroll needs a trusted anchor:** clean portraits in `data/identity/me/`. The
>     auto-collected `profile_refs/` gallery was provably polluted (faces clustered
>     into ~15 identities, mean pairwise sim 0.18). `enroll()` keeps only gallery
>     crops whose face matches the anchor → auto-cleans the dataset. Embeddings
>     cached in `data/identity/identity.npz`.
>   - **Verified on real data:** user dropped **39 portraits** (internal consistency
>     0.705). Enroll kept 10–12 matching crops, rejected the rest. **Identified Thảo
>     in 10/10 existing clips** (confidence 0.59–0.91). Thresholds tuned to
>     ENROLL_MATCH 0.40 / IDENTIFY_FACE 0.45 (true matches 0.59+, opponents <0.35).
>   - **Wired into `detect_clip`:** face identity runs first → auto-sets the side;
>     only falls back to the VLM/manual box when not confident. Endpoints
>     `GET/POST /api/video/identity/{status,enroll}`; "Ghi danh lại" button + status
>     in the profile panel. Also added a **double-click lightbox** on reference
>     thumbnails.
>   - **Deps:** `insightface`, `onnxruntime`, `scikit-image==0.24.0`; numpy kept <2
>     (insightface tried to pull numpy 2, which breaks mediapipe — re-pinned).
>   - **DB cleanup (uncommitted):** user wiped all `va_trait` (rough analysis) + the
>     polluted gallery (removed 18 wrong-person + 8 no-face crops → 12 clean Thảo
>     images). The identity photos/npz are gitignored.
>   - **Open:** user to **live-verify the auto-detected side** is correct on a real
>     clip in the app; body-re-ID path is built but not yet exercised end-to-end.

> **Resume (2026-06-14, earlier).** Built **Tab 7 "HLV trưởng" (Head Coach) — the
> Tier-2 brain, Phase 1.** This is the north-star module: a single STRICT personal
> coach for Nguyễn Bá Thảo that **consumes** the specialist reports (no re-collecting)
> and synthesises a holistic verdict + plan. Design in
> `backend/app/features/head_coach/HEAD_COACH_PLAN.md`.
>   - **Consumer, in-process.** `gather_bundle()` calls the four specialists' own
>     service functions directly (`video_service.build_report`, `training_service.report`,
>     `tracker_service.build_stats` over a 90-day window, `playbook_service.list_tactics`)
>     — no HTTP. Only `accepted` video findings reach it (VA already gates).
>   - **Model = `qwen3:14b`** (text-only reasoning, no VLM). New `HEAD_COACH_MODEL`
>     settings knob; called like `synthesize_skills` (Ollama `/api/chat`, JSON `format`
>     schema, num_ctx 16384, temp 0.3). Verified end-to-end: ~52s, sharp data-grounded
>     output (cites real win-rate/pose/training numbers). `gpt-oss:20b` & `qwen2.5:32b`
>     are also pulled locally as upgrade options — swap the knob.
>   - **Persona:** strict personal coach — problem-first, no flattery, issues measurable
>     "tăng cường" directives (train more / more playing hours / more matches singles-
>     doubles-pips / sharpen skill), in-match tactic suggestions, a knee-safe week plan,
>     and watch-items flagging thin/stale data.
>   - **Output** persisted as snapshots in `hc_assessment` (latest = current verdict);
>     generated **on-demand** (button), tab reads the latest saved snapshot — it does NOT
>     re-run on load. Endpoints: `POST /api/head-coach/generate`, `GET /assessment`,
>     `GET /sources`. New frontend tab `tabs/head-coach/` (icon 🧠, placed first).
>   - **Phase 2/3 (deferred):** review/confirm gate + snapshot history; then write-back
>     (drive Training-Center prescriptions, push tactics into the Playbook).
>   - **Open thread:** the user wiped all `va_trait` (strengths/weaknesses) + the stale
>     `overall_summary` + the test `hc_assessment` snapshot to start fresh ("phân tích
>     nhám") — will re-analyse clips. **Next: go fix the Video Analysis tab** (per the
>     user). NOTE: the DB deletions were left UNCOMMITTED (recoverable from HEAD).
>   - **Ops:** restart backend (new code) + `npm run build` (done) to see the tab.

**Seven tabs in place.** Tab 1 "Daily Tracker" feature-complete; Tab 2 "Tactical
Playbook" v1; Tab 3 "Match Stats" (named-opponent analytics); Tab 4 "Video
Analysis" — local-AI clip analysis (now **motion-aware**, see below); Tab 5
"Profile" — a read-only player dashboard; Tab 6 "Training Center" — off-table
physical program (day-by-day, see below); Tab 7 "HLV trưởng" (Head Coach) — the
Tier-2 brain (Phase 1, see newest Resume note). Stack: FastAPI + SQLite backend, React
+ Vite + TS frontend, served on one port by `start.bat`. The backend venv is
**Python 3.12** (mediapipe ships no 3.13 wheels); `start.bat` builds it with
`py -3.12`.

> **Resume (2026-06-13, newest).** Expanded & polished the **Training Center** program
> + a project-wide cleanup pass. Exercises now **39** (was ~28):
>   - **New knee-safe, TT-specific moves.** Legs: *lateral lunge* (chùng chân ngang,
>     light 2×8), *hip hinge* (chuỗi sau). Core: *plank xoay hông*, *plank chạm vai*
>     (kháng xoay), *bird-dog*. Filled the big gap — **upper body / shoulder / wrist /
>     mobility** (the program was lower-body+core heavy, weak for a stroke sport):
>     *chống đẩy tường*, *nằm sấp Y–T*, **cuộn/xoay cổ tay** (độ xoáy), *xoay ngực
>     mở sách*. The **balance day** was re-themed "Thăng bằng · vai · cổ tay" to hold
>     the upper-body work — **legs stay 3/6** (knee mandate untouched). Heavier moves
>     gated to levels 2–3.
>   - **Step-by-step instructions for ALL 39 exercises** — a `HOW_TO` dict in
>     `program.py` (`how_to_for()` → schemas/service → `how_to` field), shown as an
>     expandable "📋 Hướng dẫn chi tiết" (`<details>`) on each card + warm-up/cool-down.
>   - **Dedicated pose SVGs** for the 8 new moves (`frontend/public/exercises/poses/`),
>     mapped in `constants.ts` `POSE` (was reusing generic figures).
>   - **Cleanup / refactor** (committed earlier this session): removed dead
>     `LEVEL_RANK` + the unused `Exercise.level_min` field (`DAY_TEMPLATES` is the sole
>     source of what appears per level); `_get_row`→public `get_session_row`; full
>     audit of all features → dropped dead `analyzer.run_pose/pose_track` (111 lines),
>     deduped `_utcnow`, removed unused `APP_PORT`, profile uses shared `pct()`; dropped
>     the orphan `tracker_day_rating` table.
>   - **Ops:** restart backend + `npm run build` (frontend changed) to see it.
>
> **Resume (2026-06-13, latest).** Shipped **Tab 6 "Training Center"** — the Tier-1
> *training-load* specialist — and **live-verified** it (user completed Day 1, sync
> confirmed). Committed: `8322470` (feature) + `c884525` (DB w/ the first session).
> Design in `backend/app/features/training/TRAINING_CENTER_PLAN.md`.
>   - **v2 upgrade (4 features, separate commit):** (1) **guided workout player** —
>     full-screen step-through with countdown timers for holds (per-side split),
>     rep "Xong hiệp", rest timers, "ting"; (2) **pain/RPE feedback after each
>     session → autoregulation** — `tc_state.intensity_bias` (easy→+1, mild pain→−1,
>     strong→−2, clamp [−2,3]) shifts `scaled_target` for future sessions; (3)
>     **streak + 35-day heatmap** in the tab; (4) **warm-up/cool-down** (untracked,
>     in SessionOut) + per-exercise **"đổi bài" (substitute)** / **"bỏ (đau)" (skip,
>     logged)**. New cols via `seed.migrate` (pain/rpe, skipped, intensity_bias).
>   - **Knee-safe, quad-priority** (user has grade-1 knee OA; doctor: strong quads
>     offload the knee). NO deep squats / lunges / jumping. ~28 low-impact exercises;
>     every leg day LEADS with quad work (quad set, straight-leg raise, short-arc
>     quad), cycle weighted to legs 3/6. Progression = reps / time-under-tension only.
>   - **Day-grid (BetterMe-style)**, day_index decoupled from the calendar; 3 levels
>     (Căn bản → Sức bền & ổn định → Chuyên biệt) × 21 sessions, sequential unlock +
>     auto level-up. After the top level it enters **endless maintenance** — repeats
>     in cycles (Vòng N) with capped progressive overload (+2 reps / +5s, plateau
>     after 3). Header shows "· Vòng N".
>   - **Daily Tracker sync from a cutover date** (option A): union read-path, no
>     duplicate rows (legacy checks before cutover untouched; done TC sessions count
>     from it forward). Grid's Physical row = read-only mirror that **opens a session
>     detail popup on click** (`GET /session-by-date`). Default timeline Week→Month.
>   - **Head Coach contract** `GET /api/training/report` (load/adherence/volume).
>     **Adaptive prescription** reads the `va_skill` ledger directly (weak
>     stance_posture/footwork/physical → corrective exercise w/ reason). Profile tab
>     has a Training Center card.
>   - **Open items:** GIFs are placeholders → drop real ones in
>     `frontend/public/exercises/<key>.gif`. The **Head Coach (Tier-2)** is the
>     intended long-term owner of "what next" (will read `/report`). Undecided:
>     should a <70%-complete session count as a physical day (now: completing = 1
>     physical day; yellow at ≥70%). Caveat to user: not medical advice — stop on pain.
>   - **Ops lesson:** after adding a feature, **restart the backend** (a stale uvicorn
>     served old code → `/api/training/*` 404'd into the SPA → "Unexpected token '<'").
>
> **Resume (2026-06-13, earlier).** Small Daily-Tracker session on top of the big
> Video Analysis work below: added **pips-rubber opponent tracking** ("đánh gai") —
> `tracker_player.plays_pips` (per-player by name), opponent-picker toggle + 🏓 chips,
> and a **🏓 vs Pips** record card in the Analysis panel; seeded 3 pips opponents.
> Committed `4ac9843`. No open threads here — the next real milestone is still the
> Tier-2 Head Coach (see below).
>
> **Resume (2026-06-09).** Big Video Analysis session — `ANALYSIS_UPGRADE_PLAN.md`
> **Phases 1–4 done** (Phase 5 split-step is the only one left, advanced/experimental),
> plus the table-ROI model swap and a round of **live-verified quality fixes**. All
> committed. The qualitative analysis is now trustworthy and strict; the remaining
> work is point-level counting (deferred, see below) and the Tier-2 Head Coach.
>
> **Shipped this session (in order):** self-critique pass + clip `focus`
> (`10e3f47`); evidence thumbnails w/ skeleton (`0dd6b8f`); progress trends
> (`5c1b8e9`); ball/table tracking (`b6d393d`); **table ROI = user's trained
> YOLOv8-seg** reused from video_studio_v3 → `data/models/roi_seg.pt`, needs
> `ultralytics` (`f04b229`); pose-metric rotation fix (`fc2be62`); PROGRESS
> (`2828b99`); **pre-interpret pose numbers** so the VLM stops misreading angles
> (`39b9f64`); **duration-scaled sampling + honest cross-clip trends** (`f2ad75a`);
> **third finding state "Chưa quan sát"** (`4ee92a9`); **qualitative tactical
> analysis** — serve variety + tendencies, no counting (`e3964d1`); **strict,
> no-flattery coaching prompt** (this commit).
>
> **CONFIRMED live (browser):** end-to-end run works — self-critique note, evidence
> thumbnails (skeleton drawn) with jump-to-time, focus, YOLO table zones, progress
> table all render. The knee-misread + sparse-long-clip + nonsense-trend bugs the
> user spotted are fixed.
>
> **Strict-prompt verification (2026-06-09, DB-free re-run on clip #10):** the
> no-flattery prompt is a clear, accurate improvement over the old flattering output.
> Before: summary praised "tư thế chuẩn, khuỵu gối tốt, trọng tâm thấp" (wrong) + 4
> praise-strengths. After: summary is problem-first ("trọng tâm cao do gối không
> khuỵu đủ + chiến thuật đơn điệu"), **3 concrete weaknesses each with "Cách sửa:"**
> (forehand knee 162.8° now correctly a weakness — the misread is gone; footwork;
> monotone tactics), tactical note names the gap ("dễ bị bắt bài"), and the only
> "strength" was a non-observation that the `_unobserved` filter reclassifies to
> "Chưa quan sát" on save. Self-critique dropped 0 (findings now well-grounded).
> **Conclusion: qualitative output quality is good/trustworthy — clear to build the
> Head Coach on it.** Pending the user's go-ahead (asked at end of 2026-06-09).
>
> **DEFERRED on the user's call (don't build until asked):** counting winners /
> unforced errors / short-vs-long-serve win% — needs human-confirmed point logging
> to be trustworthy (auto-detection from sparse video is unreliable). The agreed
> shape when resumed: *AI proposes points (audio-gap segmentation + serve-zone guess)
> → user confirms in a review gate → compute stats*. Also Phase 5 (split-step, needs
> ≥60 fps + opponent tracking) and a TrackNet ball model (drop at
> `data/models/ball_tracknet.onnx`) stay optional.
>
> **Next big milestone:** the Tier-2 **Head Coach** (north star) — all specialist
> data (skills, traits, metrics/trends, tactical notes, tracker/match stats) is now
> ready to consume. Note: re-analysing a clip is required for the new data
> (evidence/metrics/ball/tactical) to populate — older clips predate it.

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
analyzing → done | error | stopped`. The native file picker is per-monitor-v2
DPI-aware so the dialog is crisp on scaled displays.

**Review gate + skill ledger (2026-06-08).** AI findings no longer auto-save: an
analysis lands as `done` with findings in status `proposed`; the user reviews
them (tick to keep, edit text, or untick to reject — "duyệt cả clip + sửa lẻ")
and only `accepted` findings count. A new `va_skill` table is the systematic
ledger — one row per aspect (serve/receive/forehand/backhand/footwork/
stance_posture/tactics/mental/physical) with a 1–10 rating + status + assessment
+ priority, synthesised from accepted findings by the local text model and
hand-editable. `GET /api/video/report` is the machine-readable "brain view"
(skills + strengths/weaknesses/priorities). Old findings were migrated to
`proposed` (not auto-accepted). Honest limit: ratings are the model's estimate
from the written findings, not a calibrated score; the user's edit is canonical.

**Tab 5 "Profile"** — a read-only dashboard centred on Nguyễn Bá Thảo that
assembles existing endpoints (no new backend): header (avatar from the identity
gallery + basics + AI overall summary), a hand-rolled SVG **skill radar** (9
axes) + rating bars, strengths/weaknesses, improvement priorities, plus a
**competitive snapshot** (win rate overall + by opponent level, from
`/tracker/match-stats`) and a **training snapshot** (days trained / hours /
physical days, from `/tracker/stats`) with a 30/90/365-day/all range selector.
Editing skills/findings stays in Video Analysis; Profile mirrors them read-only.

**Speed + control (2026-06-08).** Clip trimming now uses the GPU: `trim_segment`
tries full-GPU (NVDEC decode + NVENC encode) → NVENC-only → CPU `libx264`,
falling back per tier (verified ~9–10× on this RTX 5060 Ti). While a clip is
processing/analyzing the detail view shows an **elapsed timer + estimated
progress bar** (start time stored server-side in `va_clip.processing_started_at`,
so it survives reloads; the bar caps at 95% until the job truly finishes). A
**Stop** button cancels a running job cooperatively: the clip flips to `stopped`
immediately and the worker discards its result after the current step (the
in-flight Ollama call finishes in the background but nothing stale is saved).

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
  autocomplete, Travel/Rest; each set score is one match record. An opponent can
  be flagged **"đánh gai"** (pimpled rubber) — a property of the player by name
  (`tracker_player.plays_pips`), toggled in the opponent picker, shown as a 🏓
  chip; defaults off for everyone unless flagged.
- **Physical Training** → checklist (Wall Sit, Sit-ups, Plank, Squats, Obliques,
  Stretching); cell turns yellow at ≥70% ticked.
- **Overall** is auto-generated per day: green (a green-row trained), else yellow
  (any other data), else red (a past tracked day with no data), else blank
  (today not yet logged / future / before tracking began).
- Future days are not editable. App opens on the latest week that has data.
- **Analysis panel**: summary cards (days trained, physical days, training time,
  Singles / Doubles / All-matches win rates, **🏓 vs Pips** — record vs
  pimpled-rubber opponents) + a comparison chart (Columns or Line, default Line;
  metric selector) + training-time-by-category bars.
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

## Final goal (north star)

The whole project converges on a **two-tier coaching brain**, and every tab is a
data source feeding it. This is the design contract — keep new work consistent
with it.

**Tier 1 — Specialist coaches (data producers).** Each tab is a focused coach
that observes one slice of the player and writes structured, machine-readable
data into the DB. They do *not* give the final verdict; they produce evidence.
- **Video Analysis = the video-analysis specialist coach.** Watches clips, finds
  strengths/weaknesses, and persists them as systematic records: accepted
  findings (`va_trait`) + the per-aspect skill ledger (`va_skill`, 9 aspects with
  1–10 ratings). `GET /api/video/report` is its structured "brain view" output.
  A deep upgrade of this coach (motion-aware sampling, stroke segmentation,
  evidence-grounded findings, metric time-series for progress) is designed in
  `backend/app/features/video_analysis/ANALYSIS_UPGRADE_PLAN.md` — phased,
  not yet implemented.
- **Daily Tracker / Match Stats** = the training- and match-load record: what was
  trained, how much, match results by opponent level, win rates, physical work.
- **Tactical Playbook** = the player's known tactics and tendencies.
- **Training Center** = the off-table physical-training specialist: the structured
  daily program, what was completed, adherence/volume by muscle group, current
  level. `GET /api/training/report` is its structured "brain view"; it also reads
  the Video Analysis skill ledger to prescribe corrective exercises (cross-feeding
  between specialists, still all consumable by the Head Coach later).

**Tier 2 — Head Coach ("HLV trưởng", the brain) — TO BE BUILT LATER.** A future
top-level coach/tab that *reads everything* the specialists wrote — all daily
tracking metrics + the strengths/weaknesses/skill DB from the video-analysis
coach (and the other tabs) — and synthesises the holistic verdict: overall
assessment, priorities, and a concrete training plan. It is a *consumer* of the
specialist data, not a re-collector. It will lean on the same local-AI stack.

**Implication for ongoing work:** anything a specialist coach learns must be
saved in a structured, queryable form (tables + a `/report`-style endpoint), so
the Head Coach can later read it without scraping UI or re-running analysis. The
review/confirm gate matters here — only *accepted* findings should reach the
brain. Keep the data contract stable; build the Head Coach tab afterwards.

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

### 2026-06-13 — Tab 6 "Training Center" (off-table physical program)
Built per `backend/app/features/training/TRAINING_CENTER_PLAN.md` (design doc agreed
with the user across several rounds of critique). The Tier-1 *training-load*
specialist coach. Committed `8322470` (feature) + `c884525` (DB). **Note:** the
curriculum below was the initial build; it was then **redesigned knee-safe /
quad-priority** + given endless maintenance cycles + a click-to-view popup — see the
top Resume note for the shipped state.
- **Model (`tc_*`).** `tc_state` (current_level, unlocked_levels, level_since,
  **cutover_date**); `tc_session` (level + day_index, NOT a calendar date; status
  unlocked→done; `done_on` = calendar date completed); `tc_session_item`
  (exercise_key, target snapshot, done, is_prescribed, rx_reason).
- **Program (`program.py`, static).** ~15 exercises (TT-relevant: rotational core,
  lateral legs, split-step, single-leg balance; no chest/biceps) each with a
  table-tennis benefit + form cue; 3 levels (Foundation→Explosive→TT-Specific),
  21-session programs, day-cycle Legs→Core→Balance, exercises chosen per level by
  `DAY_TEMPLATES` (later expanded to 39 exercises + per-exercise `HOW_TO` steps).
- **Progression.** BetterMe-style sequential unlock (finish Day N → unlock Day N+1;
  finish a level → unlock the next). No demotion / re-locking (we trust the user).
  day_index is decoupled from the weekday calendar (no streak resets).
- **Daily Tracker integration (option A, from a cutover).** Completing a session
  feeds the physical-day signal via a **union read-path** in `tracker/service.py`
  (`_load_range` loads `training_service.physical_day_map`; `_physical_dates` unions
  legacy checks before the cutover with done sessions from the cutover forward — no
  duplicate rows, can't drift). Overall/`days_physical`/stats/breakdown/export and
  the grid's earliest/latest-data bounds all updated. The grid's Physical row is a
  read-only mirror ("💪 4/5 · …") from `WeekResponse.physical_cutover` forward;
  legacy past days stay editable and untouched.
- **Head Coach contract.** `GET /api/training/report` — level, adherence
  (last 7/30d, days-since-last), volume by day-type + muscle group, recent sessions,
  a data-driven coach summary. A Training Center card was added to the Profile tab.
- **Adaptive prescription.** `prescription_for` reads the `va_skill` ledger directly
  (no Head Coach, no HTTP): a weak `stance_posture`/`footwork`/`physical` aspect →
  one corrective exercise injected into the open session (`is_prescribed`, with a
  transparent `rx_reason` from the assessment); skipped if the base session already
  includes it. Best-effort (any failure → no prescription).
- **Frontend** `tabs/training-center/` (icon 💪, replaced the disabled "Training
  Plan" slot): header + progress bar, day grid, session detail with Check-done (+a
  WebAudio "ting"), level switcher, weekly summary. **GIFs are placeholders** (🏋️
  fallback; real files go in `frontend/public/exercises/<key>.gif`).
- Verified: 3 backend smoke tests (level-up; physical union → days_physical/Overall;
  prescription + report) + frontend `tsc` clean. Also: Daily Tracker default
  timeline Week→Month.

### 2026-06-13 — Daily Tracker: pips-rubber opponents ("đánh gai") + vs-pips analysis
Per the user: track whether an opponent plays pimpled rubber, as a property of
the **player by name** (not per match) — "không tick thì theo tên đối thủ". All
existing players default to non-pips; future pips opponents get flagged once.
- **Backend**: new `tracker_player.plays_pips` column (idempotent ALTER in the
  tracker seed `migrate()`, mirroring video_analysis). `PlayerIn/PlayerOut` +
  `MatchOut.opponent(2)_plays_pips`; `StatsResponse.vs_pips` (a `MatchStats`
  over playing matches where either listed opponent plays pips — `build_stats`
  now eager-loads the opponent relations). `create_or_get`/`update_player` carry
  the flag.
- **Frontend**: `PlayerPicker` gains a `pipsEditable` prop — opponent pickers
  show a `Gai?`/`✓ Gai` toggle (persists via `PUT /players/{id}`) + an add-new
  "🏓 đánh gai" checkbox; pips players show a 🏓 chip in the dropdown, selected
  pill, and the match-list line. `AnalysisPanel` adds a **🏓 vs Pips** card.
- **Data**: seeded 3 pips opponents — Tuấn gỗ (above), Ánh Loan (above), Khoa BB
  Thanh Niên (equal). Committed `4ac9843`.

### 2026-06-09 — Video Analysis: live-verify fixes + qualitative tactical analysis
Driven through the browser by the user; several real quality issues found and fixed,
plus a new tactical read.
- **Pose numbers pre-interpreted** (`pose_to_text` "ĐÁNH GIÁ: …", SYSTEM_PROMPT): the
  8B VLM had read knee 162.8° (near-straight) as "khuỵu gối tốt, trọng tâm thấp" —
  now code states the verdict and the model must follow it.
- **Duration-scaled sampling**: was a fixed 48 frames over any length (3-min clip =
  0.27 fps). Now ~6 fps between a 48-floor and 220-cap; montages spread across the
  timeline. Fixes "output hạn chế" on long clips.
- **Honest cross-clip trends**: only the geometric angle means (knee/lean/stance/hand)
  are comparable across clips; the length/sample-rate-dependent ones (swing speed,
  tempo, recovery, lateral sway) were producing nonsense deltas (−95%, +4077%) →
  excluded from the progress table (`METRIC_META.trend`).
- **Third finding state "Chưa quan sát"** (neutral): non-observations are kept as this
  state (not dropped, not mis-filed as weakness); excluded from strengths/weaknesses,
  the skill ledger, and profile synthesis. Review dropdown gains the option.
- **Qualitative tactical analysis** (user chose qualitative-only, no counting): VLM now
  fills `serve_variety.notes` (serve diversity — short/long/spin/placement, varied vs
  predictable) and `tactics.notes` (tactical tendencies + tactical gaps), shown as
  "🎲 Đa dạng giao bóng" + "♟️ Chiến thuật" blocks. The prompt forbids inventing
  win/loss or winner/error counts (insufficient data).
- **Strict, no-flattery prompt**: SYSTEM_PROMPT now mandates a demanding-coach stance —
  no social praise / generic "tốt/ổn/chuẩn", default to finding faults + concrete
  fixes, only call something a strength if it's genuinely notable with visible
  evidence (else leave blank), and the tactics note must call out gaps, not just praise.

### 2026-06-09 — Table ROI: reuse the trained YOLOv8-seg model from video_studio_v3
Replaced the fragile classical blue/green table detection with the user's
fine-tuned **YOLOv8-seg ROI model** (`video_studio_v3/assets/models/roi_seg.pt`,
trained on many hand-labelled table examples). It segments the *foreground* table
specifically — classical colour grabbed the whole green floor and produced wrong
placement zones.
- Copied the weights to `backend/data/models/roi_seg.pt` (6.7 MB, now tracked; the
  gitignore keeps other/large models out). Added `ultralytics==8.4.62` (pulls CPU
  torch — table detection runs once per clip, so no CUDA needed).
- New `table_roi.py`: a self-contained port of that project's `backend/roi_yolo.py`
  YOLO tier — lazy-loaded, optional (falls back to classical if the model/ultralytics
  is absent), returns 4 normalised corners (CW from TL) + confidence + area fraction.
- `ball.detect_table` now tries YOLO first (`color="yolo_seg"`), classical fallback.
- Verified: clips #8/#10 detect the foreground table at conf 0.93 (area ~0.02) →
  accurate zones; clip #3 (model didn't fire) falls back to classical. mediapipe +
  torch coexist in one process; full `analyze_file` runs clean. Honest limit: the
  ball *trajectory* is still the classical detector (only the table ROI was upgraded);
  a TrackNet ball model is still the optional next step.

### 2026-06-09 — Video Analysis Phase 4: ball + table tracking (NC1, best-effort)
New `ball.py` module, wired into `analyze_file` and persisted to `va_analysis.ball_json`
(new column, migrated). Strictly best-effort — never blocks analysis, degrades to
`available: False` with an honest note.
- **Two detector tiers, auto-picked.** Tier 1 **TrackNet ONNX** — used only if
  `settings.BALL_MODEL_PATH` (`backend/data/models/ball_tracknet.onnx`) exists AND
  `onnxruntime` imports; loaded once, CUDA provider preferred. Optional, pluggable,
  not bundled. Tier 2 **classical** — frame-difference + small round bright blobs
  (the documented fallback; noisy).
- **Table homography**: `detect_table` segments the blue/green table region, takes
  the largest contour → 4 corners (`approxPolyDP`, else `minAreaRect` fallback) →
  `getPerspectiveTransform` to a unit rectangle. `placement_zones` maps ball points
  through it into a 3×3 grid (near-net/mid/far × left/center/right).
- **Honesty gate**: the classical tier only reports `available` when a table
  homography turns its points into real on-table zones (raw noisy image-plane points
  alone tell the user nothing); TrackNet trajectories are trusted on their own. Single
  uncalibrated camera ⇒ placement zones only — **no speed/spin claimed.**
- Frontend: `AnalysisOut.ball`; a "🏓 Bóng & điểm rơi (thử nghiệm)" block in
  `AnalysisDetail` with a 3×3 `PlacementGrid` heat-grid + method/confidence/note.
- Verified on real clips (no model present → classical): table found on #3 (green,
  area 0.15) and #10 → 5–6 placement zones; #8 no table → graceful skip. Full
  `analyze_file` integration (stubbed VLM) produces JSON-serializable ball data.

### 2026-06-09 — Video Analysis Phase 3: progress tracking (metric deltas vs baseline)
Closes the committed core (Phases 1–3) of `ANALYSIS_UPGRADE_PLAN.md`. The
`va_metric` time-series (written since `3e35bda`) is now *read back* to show
improvement over time.
- **`service.METRIC_META`**: per-metric Vietnamese label + unit + which direction is
  an improvement (`up`/`down`/`neutral`) — e.g. knee flexion lower = better, swing
  speed higher = better, recovery time lower = better. The Head Coach reads the same.
- **`clip_progress(db, clip)`**: this clip's metrics vs the mean of the same metric
  over all *earlier* clips → `MetricTrend` (current, baseline, delta, %, trend
  improved/declined/flat/changed, sample count). Surfaced as `AnalysisOut.progress`
  and a "📈 Tiến bộ so với các clip trước" table + coloured `TrendChip` in
  `AnalysisDetail`.
- **`report_metric_trends(db)`**: whole-history trend (latest clip vs mean of earlier)
  → `ReportOut.metric_trends`; shown in `SkillBoard`. Additive, no break to the
  Profile tab consumer. Ordering is by the CLIP's date (join `va_clip`), robust to
  re-analysis resetting a metric row's own timestamp.
- Verified the trend logic with synthetic metrics rolled back (no data written):
  knee 155→142 = improved −8.4%; swing 1.0→1.12 = improved +12%; recovery 0.9→0.95
  = declined +5.6%. Honest limit: existing clips predate `va_metric`, so deltas are
  empty until **≥2 clips are re-analysed**.

### 2026-06-09 — Video Analysis Phase 2 (part): self-critique pass + clip focus tag
Both target *trustworthier* findings, per `ANALYSIS_UPGRADE_PLAN.md` Phase 2.
Verified by a direct pipeline run on clip #10 (`reviewed=6 dropped=1`; focus block
confirmed in the VLM prompt; `va_clip.focus` migrated into the live DB).
- **Clip `focus` tag (L8):** new `va_clip.focus` column (`serve_practice |
  footwork_drill | rally | match | free | ""`), added idempotently via
  `seed._VA_CLIP_COLUMNS`. A "Trọng tâm phân tích" dropdown in `UploadForm` →
  `ClipCreateIn.focus` → `service.create_clip` (validated) →
  `analyzer.analyze_file(focus=…)` → `call_vlm`, which injects a focus-specific
  Vietnamese instruction block (`_FOCUS_VI`/`_focus_block`) so the VLM concentrates
  on the right aspect (a serve clip isn't graded on footwork; a match clip gets a
  tactical read). Focus shown in `ClipList` + `AnalysisDetail` meta lines.
- **Self-critique pass (Pass C, S7):** after the main VLM call, `analyzer.self_critique`
  re-sends the SAME montages/frames + pose numbers + the draft findings and asks the
  model to judge each one `supported = yes|partly|no`. `_apply_self_critique` then
  **drops** unsupported findings and **downgrades** shaky ones (caps confidence ≤0.6)
  before they become `proposed` traits, and writes a `raw["critique"]` summary
  `{reviewed, dropped, downgraded}`. Best-effort (any failure → keep all unchanged);
  gated by `SELF_CRITIQUE` config knob. UI shows a "🔍 AI tự kiểm tra…" note. Backend
  logs `[video_analysis] self-critique: reviewed=… dropped=… downgraded=…`.
- Honest limit: the critique is the same 8B VLM grading itself — it reduces, not
  eliminates, over-claiming; the human review gate stays the final word.
- **NC4(a) annotated evidence thumbnails:** `analyzer.annotate_pose_frame` draws the
  MediaPipe skeleton + the playing-arm elbow and knee angles (ASCII caption
  `t=… FH knee=150 elbow=56`) on each shown stroke's contact frame, zoomed to the
  player via `_pose_bbox`. `analyze_file` returns an `evidence` list; `analyze_clip`
  saves them as clip-scoped `evidence_<clip>_<stroke>_<hex>.jpg` under `VIDEOS_DIR`,
  and maps each finding's `t_ref` to the nearest one → `va_trait.evidence_json`
  (new column). Served by `GET /clips/{id}/evidence/{thumb}` (filename validated,
  no traversal); shown as a clickable thumbnail next to each finding in
  `AnalysisDetail` (seeks the video too). Cleaned on re-analyse + clip delete.
  Verified end-to-end (4 thumbnails, skeleton visibly drawn, mapping + serve-path OK).

### 2026-06-09 — Video Analysis deep upgrade: motion-aware pipeline (Phases 0–1, B, evidence, persistence)
Executed the `ANALYSIS_UPGRADE_PLAN.md` first phases. Three commits, all additive
and idempotent; existing data preserved. **Committed but not yet verified live.**
- **`ad94665` Phase 0–1 (motion):** `analyzer.py` reworked to *see motion* instead
  of evenly-spaced stills. `sample_timestamped` (one timestamped decode) +
  `decode_at_times`; `detect_impacts` (audio ball-contact onsets); unified
  `analyze_pose` (one MediaPipe pass, replaces run_pose+pose_track) +
  `aggregate_pose` measuring posture **during strokes** (lateral_sway stays
  whole-clip — footwork range is between strokes); `segment_strokes` + canonical
  phasing; per-stroke montages (`montage_strip`/`stroke_montage_b64`). `analyze_file`
  feeds the VLM montages + stroke context with a fallback chain: pose-stroke
  montages → impact-anchored montages → even stills. Fixed the progress-timer
  timezone bug (`parseServerTime`, was showing +7h).
- **`9c4ceeb` Phase B + dynamics:** `motion_energy` + `corroborate_impacts` reject
  neighbour-table audio cross-talk (keep only impacts coinciding with player
  motion — verified 7→6 on a hall clip). `stroke_dynamics`: swing speed / tempo /
  recovery time, surfaced to the VLM + metrics.
- **`3e35bda` evidence + persistence + clean findings:** per-finding `t_ref`
  (timestamp) + `confidence` in the VLM schema/prompt → `va_trait.t_ref` →
  clickable "▶ m:ss · %" chip in `AnalysisDetail` that seeks the clip video. New
  `va_metric` table + `va_analysis.strokes_json`/`metrics_json` (the structured
  spine the future Head Coach reads). Empty "không quan sát rõ" non-observations
  are dropped before becoming traits.
- Verified end-to-end during the session: near-camera clip → `path=pose strokes=4
  impacts=7→6 montage=True`, clean non-contradictory findings; far clip falls back.
- Honest limits carried forward: hand FH/BH is a heuristic guess; phasing window is
  valley-to-valley (knee angle still a bit high); motion-energy cross-talk filter is
  best-effort (half-crop). Pipeline language note: **VLM prompts stay Vietnamese**
  (content); code comments/logs in English (see memory).

### 2026-06-08 — Review gate + skill ledger, Tab 5 "Profile", GPU trim, progress bar, stop
- **Review/confirm gate**: `va_trait` gained `status` (proposed|accepted|rejected),
  `ai_text`, `reviewed_at`; `va_clip` gained `reviewed_at`. `analyze_clip` now
  writes findings as `proposed`; new `review_clip` + `POST /clips/{id}/review`
  accept/reject (with inline edits). `regenerate_profile_summary` and the trait
  board now consider only `accepted`. Idempotent `migrate()` ALTERs the new
  columns; existing findings → `proposed`.
- **Skill ledger**: new `va_skill` table (9 aspects, rating 1–10/status/assessment/
  priority), seeded in `seed.py`. `analyzer.synthesize_skills` (Ollama structured
  output, text model) fills it from accepted findings; `GET/PUT /skills`,
  `POST /skills/regenerate`, `GET /report`. Frontend: `SkillBoard` (radar-less bar
  view with edit + regenerate) in Video Analysis; review panel in `AnalysisDetail`.
- **Tab 5 "Profile"** (`frontend/src/tabs/profile/`, registered in `registry.ts`,
  icon 🪪): read-only dashboard — SVG `SkillRadar`, bars, strengths/weaknesses,
  priorities, competitive snapshot (`/tracker/match-stats`), training snapshot
  (`/tracker/stats`), range selector. Avatar prefers a manually-added gallery
  image (`source_clip_id == null`). No backend changes — pure assembly.
- **GPU trim**: `analyzer.trim_segment` 3-tier (full-GPU NVDEC+NVENC → NVENC-only
  → CPU libx264), ~9–10× faster on the RTX 5060 Ti.
- **Progress bar + timer**: `va_clip.processing_started_at` (new column) set when a
  job starts; `AnalysisProgress` component shows elapsed + estimated bar.
- **Stop**: in-memory cancel registry + `request_stop` + `POST /clips/{id}/stop`;
  cooperative checks in `detect_clip`/`analyze_clip`; new `stopped` status.
- Added a manual portrait `Nguyễn Bá Thảo.jpg` to the identity gallery (avatar).
- Also recorded the project's **Final goal** (two-tier coaching brain) and the deep
  **Video Analysis upgrade plan** (`ANALYSIS_UPGRADE_PLAN.md`) — design only.

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
