# Refactor plan — Road To E (review of 2026-10-15)

Read-only review of the whole source on 2026-10-15 (user: "review toàn bộ source
code, restructure, refactory, và clean up nếu cần. bảo đảm source luôn clean,
dễ enhance"). Line numbers are as of commit `2649cce`.

**Status 2026-10-16 — Phase 0 and Phase 1 done** (details in PROGRESS.md):
golden tests `tests/test_golden_grid.py` + `tests/test_golden_coach_context.py`
(files in `tests/golden/`, refresh with `UPDATE_GOLDEN=1`), ESLint + vitest,
reflections API/CSS/dead methods removed, no-ops + stale comments fixed.
Suspected bug 1 (GET writes training rows) is lazy materialisation by
design — pinned by a test, not changed. Suspected bug 2 (daily-item swap
undone by `_ensure_daily`) was real and is fixed in `program.alternatives_for`.
Left for the user: `git rm -r backend/scripts/imports backend/scripts/migrations`
(blocked by the tool's permission guard). Next: a few days of normal use,
then Phase 2. Line numbers below are pre-cleanup and drift slightly.

Sizes: backend 13.3k lines of Python (50 files, 33 test files / 5.3k lines),
frontend 14.7k lines of TS/TSX (99 files) + 6.2k lines of global CSS.

## 1. Verdict

The code is in decent shape, not "dirty": every feature follows the same
models / schemas / service / router / seed layout, 187 tests pass with no
warnings, there is no `any`, no dead endpoint on the backend, ruff only flags
cosmetics. The real problems are three:

1. **God files.** `tracker/service.py` (2706 lines) mixes 13 concerns;
   `head_coach/service.py` 1778; `training/program.py` 941 (600 of data);
   `MatchEditor.tsx` 878, `PointCharter.tsx` 688, `match-stats/index.tsx` 582,
   `TournamentSection.tsx` 603, `database/index.tsx` 529.
2. **Duplication.** W/L tallies written 4 ways, "train-with-coach session"
   lookup in 5 places, the LLM background-job lifecycle copied 5×, the
   3-second polling loop copied 5×, verdict vs recap rendering ~10 twin
   blocks, four Player shapes on the frontend.
3. **No safety net on the frontend.** No ESLint (9 `eslint-disable` comments
   are inert), no test runner, the generated `shared/api/schema.d.ts` is
   tracked but imported nowhere while 90 of 136 hand-written types mirror a
   backend schema by name.

## 2. Objective tool output

- **ruff** (`uvx ruff check app tests --select F,E,W,I,B,UP,SIM,C4`): 585
  hits — 364 E501 line-too-long (ignore), 112 B008 (FastAPI `Depends`, false
  positive), 34 B904 raise-without-from (routers), 28 I001 import order,
  10 E402 (tests/conftest.py, deliberate), 2 F401 unused imports
  (`tests/test_matchlog.py:8`, `tests/test_tournament_link.py:9`), 4 E741
  `l` as a name, 2 SIM105, 3 SIM102, 1 B905 (`service.py:960` zip without
  strict), 1 B007.
- **knip** (frontend): unused exports `READ_ONLY_MESSAGE`
  (`shared/api/client.ts`), `LOCAL_CONFIG` (`shared/config.ts`); ~30 exported
  types used only in their own file (head-coach `Source*`, `CellData`,
  `RatingBucket`, `ServeStat`, `PointNote`, `TileStatus`, …).
- **CSS classes with no TS/TSX reference** (865 classes scanned, template
  prefixes like `level-${}` excluded): `tactics.css` `.tac-reflect*` block
  (382-435), `.ml-board`, `.ml-rally`, `.ml-rs-wrap`, `.ml-stage-title`,
  `.ml-pt-sc`, `.ml-pt-rally`; `training-center.css` `.tc-ex-thumb-ph` (223),
  `.tc-wp-thumb-ph` (618).
- **Dead frontend API methods** (0 callers, verified by grep):
  `tactics/api.ts` `getReflections`, `addReflection`, `updateReflection`,
  `deleteReflection`, `updateServe`, `deleteServe`, `updateNote`. The
  backend `/reflections` routes (`tactics/router.py:49-…`) are therefore
  unreachable from the GUI (the "My analysis" section was dropped
  2026-10-10). Keep the `tactic_reflection` table and its rows.
- 87 "removed / retired / legacy / replaced" narrative comments and 46
  "(user 2026-…)" dated quotes in code; history belongs in PROGRESS.md.
- pytest: 187 pass, no deprecation warnings. Deps pinned (fastapi 0.115.6,
  SQLAlchemy 2.0.36, pydantic 2.10.4, httpx 0.28.1).
- Tracked but obsolete: `backend/scripts/imports/*` (4 one-off sheet
  importers that CLEAR tracker rows for a date window) and
  `backend/scripts/migrations/*` (2 one-off migrations already folded into
  `seed.migrate`). Keep `dump_openapi.py` and `sync_prepare.py`.

## 3. Backend findings — tracker (`app/features/tracker/`)

### 3.1 Seams in service.py → proposed `service/` package

`__init__.py` re-exports every current public AND test-used private name
(`_coach_sessions`, `_result_letter`, `_fold`, `MATCH_STATS_FLOOR`,
`RACKET_MINUTES_PER_SET`, `PHYSICAL_ITEMS`, `SESSION_NOTE_TAGS`, the
`rating` re-exports at 18-25) so `service.X` keeps working in router.py,
`head_coach/service.py:39`, `tactics/service.py:36` and the tests. No test
monkeypatches tracker service, so a facade is safe.

| Module | Contents (service.py lines) |
|---|---|
| `periods.py` (leaf) | `_date_range` 2625, `_first_of_month`/`_next_month`/`_last_of_month`/`_bucket_ranges` 1918-1954, `_WEEKDAYS` 1701 |
| `tally.py` (leaf) | `_result_letter` 202, `_result_of` 1740, `_blank_match_stats`/`win_rate`/`_tally`/`_finalize_match_stats` 1704-1759, `_is_vs_pips` 1762, `_playing_matches` + `_NEWEST_FIRST` 1777-1793 |
| `text.py` (leaf) | `_fold` 382 (also removes the local-import cycle workaround in `seed.py:77,96`) |
| `players.py` | 366-614 |
| `matches.py` | `tournament_default_event` 310, `match_to_out` 323, `get_or_create_event` 620, `normalize_handicap_pattern` 1714, `last_handicap_vs` 1724, `_annotate_elo` 951, `list_player_matches` 1796 |
| `grid.py` | physical items 43-80, racket 96-136, formatting 186-307, bounds 635-684, overall colour 687-754, `RangeData`/`_load_range`/`_physical_dates` 760-830, `_grid_cells` 836-945, `build_week` 969-1013 |
| `export.py` | 2619-2706 |
| `journal.py` | session-note constants 139-183, CRUD 1016-1096, journal 1099-1307 |
| `boards.py` | tasks 1310-1419, memos 1422-1479 |
| `coaches.py` | constants 82-94, 1482-1696 |
| `stats.py` | `build_stats` 1815-1912, `build_breakdown` 1957-2020 |
| `match_stats.py` | 2023-2442 |
| `rating_analytics.py` | `build_rating_breakdown` 2448-2569, `elo_by_opponent` 2572-2616 |

Cross-group dependencies the leaf modules absorb: `_fold` (players, coaches
1510, grid 887, seed); `_level_of`/`level_from_points` (match_to_out,
`_h2h_accumulate` 2153/2172, `build_handicap_split` 2424); `_date_range`
(stats 1816, breakdown 1991, trend 2250); `_bucket_ranges` (breakdown, trend,
rating breakdown); `_annotate_elo` (week view + `list_player_matches`);
`_grid_cells` → `earliest_data_date` 942 and a direct `Coach` query 860-863;
`_is_vs_pips` (stats + h2h); `racket_minutes_by_day` (overall colours +
stats).

### 3.2 Dead / legacy / no-op

- `GET /session-notes/active` (router.py:451-456): no frontend caller.
- Advice `is_done` lifecycle retired (models.py:224-227) but PATCH still
  handles it (service.py:1072, schemas.py:389); frontend types still declare
  it (`daily-tracker/types.ts:138,151`).
- `PlayerIn.level` accepted then ignored (service.py:474-476, 525); the
  Database tab still echoes it (`database/index.tsx:333,376`).
- `PlayerOut.resnapped_matches` (schemas.py:146) never read by the frontend.
- `MatchIn.order_index` (schemas.py:256-260) is test-only input.
- `MatchStatsResponse.trend` + `with_trend`: HTTP route always passes False
  (router.py:594); only head_coach reads `.trend` in-process.
- Re-exports at service.py:18-25 exist only for router/tests.
- Legacy paths still running: `Category.type != "session_note"` filter
  (786), note-equals-coach-name guard (887), duplicate-row collapse in
  `upsert_activity` (router.py:127-131) though a unique index exists,
  one-time migrations `_seed_coaches_and_backfill` / `_rebuild_match_player_fks`
  (seed.py:90-198).
- No-ops: `over=max(0, 1 - size)` (1577), `p.is_current = False` (1592),
  "unreachable" fallback (1227), `ELO_DOUBLES_MULT = 1.0` (rating.py:44).
- `_ensure_activity_unique_index` (seed.py:207-214) returns True every run
  because of `IF NOT EXISTS`, so `migrate` commits on every startup.

### 3.3 Duplication

- W/L: `_result_letter` 202, `_journal_result_token` 1136-1139, hand-rolled
  count in `build_breakdown` 1982-1986, `_trend_buckets` 2253-2257;
  `build_handicap_split` output 2432-2437 ⊂ `_record_tail` 2103.
- Date ranges: `build_week` 978-979 re-implements `_date_range`;
  `Match.date >= a, <= b` at 797, 2047, 2094, 2411, 2504, 2597.
- Train-with-coach lookup: `has_coach_session` 1025, `_journal_coach_names`
  1106-1122, `_coach_sessions` 1489-1497, seed.py:105, router.py:139.
- Package / per-session coach lookups: 1110-1114, 1528-1533, 1537, 860-863,
  seed.py:84, 117.
- Eager-load option sets: 799-804, 1787-1792, 1181-1185, rating.py:427-431;
  `Match.is_nonplaying == False  # noqa` ~10×. `_NEWEST_FIRST` re-spelled 1735.
- Same-name rules: case-insensitive scans 482-485 / 514-521 vs `_fold` in
  `create_coach` 1509-1511; blank-name validators ×4 (schemas.py:54, 125,
  481, 495).
- Per-day minute sums 1833-1838 / 1973-1976 / 868-872; racket totals
  728-733 / 922-924 / 1891-1893; days-trained rule 1873-1879 vs 2002.
- Match batch-load 2500-2509 vs 2594-2599; `build_handicap_split`
  2406-2417 re-implements `_query_named_matches`; `_level_of` 468 vs
  `rating._snap_or_current` 294.
- Vocabularies: rounds (`ROUND_SHORT` 222, rating.py 91-96, schemas.py:271),
  disciplines (service 213, 2051; rating.py 435; schemas.py 248;
  router.py 583) → one `constants.py`.
- Router copies payload field-by-field in `create_match` / `update_match`
  (router.py:193-216 vs 240-256); get→LookupError→mutate→return-list
  repeated across tasks and memos (1375-1464).

### 3.4 Smells

- Business logic in router: `upsert_activity` 119-180 (coach validation,
  ★ strip, delete-on-empty), `create_match`/`update_match` 184-262,
  `_next_order` 24, `set_physical_checks` 298-308, `upsert_day_note`
  312-327, `list_events` 488-493, `list_categories` 39.
- Mixed error contracts: `update_player` returns None,
  `delete_session_note` returns bool, others raise `LookupError`;
  `create_session_note` returns ORM while tasks/memos return schemas;
  `delete_match` 204 on missing; `reorder_memos` → 409 where others → 400.
- Functions > 80 lines: `_grid_cells` 836-945, `_h2h_accumulate` 2127-2232,
  `build_match_stats` 2273-2388, `build_rating_breakdown` 2448-2569,
  `build_stats` 1815-1912, `rating.replay` 411-523.
- Magic numbers: `ranked[:50]` 438; 800 / 7 in `_rank_band` 446-451;
  `remaining <= 2` 1597; 999 sort fallback 64; `.limit(20)` router.py:493;
  export widths 26/18 (2700-2702); `MATCH_STATS_FLOOR` 2034,
  `_MY_ANCHOR_DATE_DEFAULT` rating.py:183.
- `export_xlsx` local `rating` shadows the module (2690).
- Stale comments: seed.py:237 ("see service ELO_KIND_MULT" → rating.py:45);
  models.py:97-99 (Player `level` "editable"); schemas.py:109-110, 389, 407,
  532; service.py:1 docstring covers ~20 % of the file.
- Separate seam: tournament placement code in rating.py:56-176
  (`placement_bonus`, `deepest_decided`, `derive_*`) belongs to the
  tournament feature; `tactics/service.py:35` imports private `_ROUND_NAME`.
  Import cycle at rating.py:389 — medium risk, low value, skip for now.

### 3.5 Test gaps

No test: `build_breakdown` and week/month `_bucket_ranges`; `export_xlsx`
(CSV touched once, test_session_notes.py:84); `set_physical_checks`,
`/physical-items`, `upsert_day_note`, `list_events`; `note_snippet`,
`format_physical_cell`; `has_data_between`; player dedupe / rename clash;
`default_coach_id` fallback; `upsert_activity` ★-strip for per-session
coach; `set_match_note` when the holder moves. `_grid_cells` only via
`/weeks` (4 hits) — the riskiest refactor target; **add golden tests for
`build_week` cells and CSV export first.**

## 4. Backend findings — head_coach, training, tactics, tournament, core

### 4.1 Structure

- Pattern breakers: `training/program.py` (static catalog), `tactics/matchlog.py`
  (second service + router section 156-233), `prompt.py` only in two
  features, inconsistent `__init__` docstrings.
- Seed naming: tracker `seed_categories` vs others `migrate`
  (`registry.py:36-42`); `tactics/seed.py:45-52` and `head_coach/seed.py:14-20`
  do stuck-job recovery inside "migrate".
- Private cross-imports: `tactics/service.py:15-20` imports `_ollama_chat`,
  `_hdc_vi`, `_coach_note_dicts`, `resolve_model` from head_coach (tests patch
  them on the tactics module, `tests/test_tactics.py:133-378`);
  `tactics/service.py:35` → `rating._ROUND_NAME`; `tournament/seed.py:7` →
  `core.sqlite_migrate._table_columns`.
- Cross-model queries: head_coach queries `TrainingSession` (42, 978-987,
  1066-1074), `DayNote`/`SessionNote` (394-432, 1121-1134); raw SQL on the
  retired `va_profile` table with bare except (227-237); `core/syncer.py:33`
  hard-codes tracker table names. Circular imports worked around with local
  imports: tracker↔training (`tracker/service.py:41, 660`),
  tracker↔tournament (`rating.py:390`, `service.py:317`).
- **Missing shared layer** → `app/shared/`: `ollama.py` (`resolve_model`,
  `_ollama_chat`, `_call_with_empty_retry`, `/api/ps` probe), `jobs.py`
  (generating→done/error lifecycle + stuck recovery), `persona.py`,
  `format_vi.py` (`_hdc_vi`, `_wr`, `_dm`, `_day_label_vi`, `_LEVEL_VI`,
  `_HANDICAP_VI`), `time.py` (`_tz`, head_coach/service.py:1547).

### 4.2 Splits

`head_coach/service.py` → package, thin facade re-exporting for router;
tests monkeypatch `hc_service._call_model`, `_call_recap_model`,
`_call_chat_model`, `resolve_model` — patch targets must move with the code.
`bundle.py` 46-452 · `render.py` 455-663 + 1197-1351 (ONE section renderer
for verdict and recap) · `llm.py` 667-705, 754-762 · `verdict.py` 708-919 ·
`directives.py` 922-1036 · `recap.py` 1039-1533 · `chat.py`/`notes.py`
1536-1752 · `debug.py` 1755-1778.

`training/program.py` → `program/` package with re-exporting `__init__`:
`catalog.py` 57-401 · `how_to.py` 475-758 (or a `how_to` field / data file) ·
`schedule.py` 20-55 + 761-842 · `daily.py` 403-472 · `progression.py` 845-941.

Other > 80-line functions: `_bundle_to_text` 494-663, `_recap_bundle_to_text`
1250-1351, `gather_recap_bundle` 1093-1194, `tournament/service.py:279
build_record`, `tactics/matchlog.py:277 compute_stats`,
`tactics/service.py:366 build_context`.

### 4.3 Dead / no-op / legacy

- `open_session` returns `(session, level_complete)` with the bool always
  False (`training/service.py:117-140`); callers discard it (250, 621).
- `rpe == "hard"` → `delta = 0` no-op (342-343).
- Written-never-read columns (keep, document as audit): `TrainingSession.adapted`,
  `completed_at`, `TrainingState.level_since`, `TrainingSessionItem.done_at`,
  `HeadCoachRecap.sources_json`, `TacticPlan.sources_json`.
- `SourceSummary.video`/`.tactics` (`head_coach/schemas.py:72-74`) exist only
  so old snapshots parse. `_player_name` reads retired `va_profile` → replace
  with a Setting row.
- Stale: "local import: service pulls in httpx" (`head_coach/seed.py:15-17`,
  `tactics/seed.py:46`); `scaled_target` docstring vs inline literals
  (`program.py:868-879` vs 888-891).

### 4.4 Duplication

- Job lifecycle copied: `run_generate_job` 822-875, `run_recap_job`
  1467-1533, `run_chat_job` 1652-1724, tactics `run_plan_job` 556-611,
  `run_me_extraction_job` 240; "already running" guard 808-814, 1433-1442,
  1578-1582, tactics 542-548; `recover_stuck_jobs` 765-797 vs
  `recover_stuck_plans` 614-623; `out if isinstance(out, dict) else {}` ×3
  (842, 1504, 1691) belongs in `_ollama_chat`; tactics plan job skips
  `_call_with_empty_retry`. → one `run_llm_job(model_cls, id, build, persist)`.
- `_ollama_chat` bare `json.loads` (705), no repair; malformed reply → raw
  `JSONDecodeError` in `error_msg`.
- Persona text ×4: `head_coach/prompt.py:12-19`, recap ~179, chat 248-256,
  `tactics/prompt.py:34-42`.
- Verdict vs recap renderers: `_sn_line` defined twice (567, 1286); task
  lines 581-595 vs 1294-1307; memo/note/coach-note lines 559-565 vs
  1308-1316; results block 616-621 vs 1325-1330; by-kind 626-628 vs
  1331-1333; weekly ELO 484-490 vs 1266-1273 and 293-303 vs 1158-1168;
  `top_h2h` 352-366 vs 1169-1181; `_wr` 455-463 vs `_matches` 1218-1224;
  `_stats` 317 vs `_kind` 1110.
- Training: "cycle if maintenance else 0" ×3 (`service.py:84`, 301-305, 402)
  → `program.cycle_for`; `_simple_ex` 144-156 vs `_item_out` 159-179;
  done/total/pct ×3 (185-200, 488-495, 589-590); completed-session count
  re-implemented in head_coach (978-987, 1066-1074) → `training_service.count_done`.

### 4.5 Smells

- Errors: `ValueError` means both 409 and 400 — `start_recap` in-flight →
  400 (`head_coach/router.py:69-70`) while generate/chat → 409; recap
  messages English (1430, 1442, 1444), rest Vietnamese; training returns
  None for not-found while `complete_session` maps ValueError → 404
  (`training/router.py:134-135`). → typed `NotFound` / `Conflict` + one
  handler.
- Router logic: `training/router.py` repeats `get_session_row` + 404 ×3
  (66-73, 89-96, 111-118); `head_coach/router.py:51-52` re-validates period.
- **GET that writes:** `training_service.report` → `level_overview` →
  `open_session` → `_materialise` commits (`service.py:619-621`); the coach
  bundle calls `report` (`head_coach/service.py:389`) so every verdict/chat
  writes training rows — also in SHARE_MODE where GETs are allowed.
- Non-atomic: `complete_session` commits, then `_autoregulate` commits again
  (384-385).
- Timestamps: `_tz` only in head_coach; tactics `_plan_out` (502) and
  `ReflectionOut` return naive UTC; `tick_item` uses naive `datetime.now()`
  (277).
- **Suspected bug:** `alternatives_for` (`program.py:926-941`) excludes only
  `NO_SWAP_KEYS`, so daily staples/dumbbells (283-310) can be offered as
  swaps; `substitute_item` applies `scaled_target` not `daily_target`;
  substituting away a daily item is undone by `_ensure_daily` on the next
  GET /today (`service.py:218-246`). Test before touching.
- Magic numbers: `num_ctx` 16384 / timeout 600 (699-701), httpx 5.0 s (674,
  1764), temperatures 0.2/0.3/0.4, 41-day ELO trend (284), `[:1000]` ×4,
  `[:5]` (`tactics/service.py:489`); training -2/-1/+1 clamp (336-344),
  thresholds 4/5/3 (527-535), 365-day floor (550), 70-day heatmap (614),
  `[:10]` (592). `OLLAMA_BASE_URL` / models not env-overridable
  (`core/settings.py:17-29`).
- `_VI`-suffixed names holding English (`LEVEL_VI`, `DAY_FOCUS_VI`,
  `SAFETY_NOTE_VI`, `name_vi`, `summary_vi`, `_METRIC_UNIT_VI`) — rename
  touches API + frontend; skip.
- `_period_stats` returns a bare tuple (1059); `gather_recap_bundle` takes 8
  positionals (1093-1102); `gather_bundle` has no injectable `today` (382),
  `_bundle_to_text` calls `dt.date.today()` (644); `_tz` defined at 1547,
  used from 881.

### 4.6 Startup (`main.py`)

Order backup → `init_db` → seeds on one session (28-39), no per-seed
rollback; seed order implicit (tactics needs tracker's `Setting` first,
`registry.py:36-42`); job recovery hidden in "migrate" → explicit
`on_startup` hook list; SHARE_MODE skips backup but migrations/recovery
still write; import-time side effects (`settings.py:11`, `main.py:23-25`);
model registration coupled to routers (`db.py:40-45`); tournament backfill
trick `_table_columns(...) or {"format"}` is obscure; `syncer.py:122`
hard-codes `master`; CORS origins hard-coded (`main.py:46-54`).

### 4.7 Test gaps

head_coach: `resolve_model` fallback, `_ollama_chat` payload, `start_generate`
409 guard, `/generate` `/assessment` `/status` `/directive-progress` routes.
training: `skip_item`, `program_grid`, level advance/unlock, `_ensure_daily`
idempotence, substituting a daily item, `/program` `/levels`. tactics: HTTP
routes for facts/reflections/interview/plan, matchlog `delete_point`
renumbering, `update_point_note`. tournament: update/delete routes. core:
`add_missing_columns`, every feature `migrate()`, `logbuffer`, lifespan
ordering (conftest blocks lifespan — a seed test on an in-memory engine
closes this). **Before refactor: characterization tests on `_bundle_to_text`
and `_recap_bundle_to_text` output.**

## 5. Frontend findings (`frontend/src/`)

### 5.1 Structure

- No tab has the full index/api/types/components layout: journal has no
  api.ts/types.ts (uses `trackerApi` + daily-tracker types,
  `journal/index.tsx:13-14`, `DayCard.tsx:9-10`, `RememberPanel.tsx:11-12`,
  `TrackingPanel.tsx:15-16`; `RichArea.tsx`, `markup.tsx` in the root);
  database has no components/ (`PlayerMatchesModal.tsx` in root); helper
  files named differently per tab (`fmt.ts`, `scores.ts`, `intake.ts`,
  `vocab.ts`, `constants.ts`, `tournaments/helpers.ts`).
- daily-tracker acts as a second shared/ (~30 cross-tab imports): its `Match`
  type → tactics (5 files) + `database/api.ts:2`; `MatchRowList` →
  `database/PlayerMatchesModal.tsx:12`, `tactics/index.tsx:11` (its comment
  at line 3 "Sole consumer is the Database tab" is stale); `tournamentApi` →
  `match-stats/components/TournamentRecord.tsx:15`; tactics uses
  match-stats `RangePicker` (`tactics/index.tsx:16`); match-stats uses
  tactics `FactsPanel`/`IntakeCard`/intake (`ScoutingMeCard.tsx:7-11`);
  daily-tracker uses training-center `SessionCard`/api
  (`daily-tracker/index.tsx:18-20`). → move domain types (`Player`, `Match`,
  `Tournament`, `Memo`, `Task`, `SessionNote`) + `MatchRowList`, `RangePicker`
  into `shared/`.
- Already good in shared/: dates, format, rank, levels, disciplines, matches,
  period, fold, api client, `useLoad`/`useMutate`, Modal, Seg, SortableTh,
  EloDeltaChip, charts.
- Inline `seg-btn` markup instead of `<Seg>`: `DurationEditor.tsx:130,142`,
  `MatchEditor.tsx:709,750,794`, `TournamentSection.tsx:278,327,336,358,367`
  (the multi-select at 336 needs a `SegMulti`).
- Journal date formatters use `toLocaleDateString` (`journal/index.tsx:23-38`,
  `DayCard.tsx:69`) while `head-coach/fmt.ts` has the vi-VN formatting →
  `shared/dates`.
- Combos: `SearchPicker` (shared) and `PlayerPicker` share the
  `.player-combo` shell and blur-timer logic (`PlayerPicker.tsx:165-174` =
  `SearchPicker.tsx:110-119`); only SearchPicker has keyboard nav;
  PlayerPicker searches server-side (49-64) and has an inline add form
  (210-271). → `useComboOpen` hook + `ComboList`, rebuild PlayerPicker on it
  (async items + footer slot). Also `MatchEditor` event `<datalist>` with
  its own debounce (315-331, 811-818); Database add-player form
  (`database/index.tsx:350-371`, 408-473) duplicates PlayerPicker's → shared
  `<NewPlayerForm>`. Plain `<select>`s (`FactsPanel.tsx:125`,
  `RangePicker.tsx:145`, `SessionCard.tsx:63`, `MatchEditor.tsx:575,604,759`)
  are short fixed lists — leave.

### 5.2 Types

- `schema.d.ts` imported nowhere (0 refs to `components["schemas"]`).
- 90 of 136 hand-written exported types match a backend schema by name (58
  exact, 32 with `Out` suffix). Hand-written ones narrow literals
  (`Discipline`, `PlayerLevel`, `MatchResult`). → `shared/api/types.ts` with
  `type X = Schemas["XOut"]` + `Omit & {…}` overrides; one tab at a time.
- Player has four shapes: `Player` (`daily-tracker/types.ts:54`),
  `PlayerDbRow` (`database/types.ts:4`), `Opponent` (`tactics/types.ts:8`),
  `OpponentBrief` (`match-stats/types.ts:36`). Match: `Match`, `MatchLine`,
  `RecordMatch`, `JournalMatch`, head-coach `SourceMatch`.
- Re-inlined literal unions: `MatchLine.discipline` (`match-stats/types.ts:10`),
  `result: "W"|"L"|"T"` (13, 32, `match-stats/index.tsx:140`).
- `round` typed `string` → ~10 `as TournamentRound` casts
  (`MatchEditor.tsx:55,70,440,608`, `MatchLines.tsx:23,25`,
  `TournamentRecord.tsx:33,60`, `match-stats/index.tsx:383`) +
  `as keyof typeof DISCIPLINE_SHORT` (365).
- `StatsResponse` keeps match buckets the frontend no longer reads
  (`daily-tracker/types.ts:289-298`).

### 5.3 Oversized components → seams

- **MatchEditor.tsx (878):** helpers `defaultRound`/`ctxLabel`/`playersLabel`
  50-104 → `matchEditor/helpers.ts` (`playersLabel` duplicates
  `shared/matches.matchupOf` with different wording; `matches.ts:66` claims
  they mirror); `EloChip` + `ELO_SKIP_LABEL` 109-130 → shared/ui; handicap
  297-313 + 363-384 → `useHandicap` + `HandicapField` (JSX 737-786);
  tournament prefill 189-254, 273-293 → `useTournamentEntry` +
  `TournamentBanner` 535-598 + `RoundPicker` 599-620; edit mode 264-271,
  386-502 → `useMatchEditState`; `CellMatchList` 631-701, `ScorePad` 820-878,
  event autocomplete 315-331 + 803-819. No tests, interlocking effects — last.
- **PointCharter.tsx (688):** rules 49-77 (`setOver`, `serverFor`,
  `winnerOf`, `sameServe`) → `tactics/pointRules.ts`; `ChipRow` 79-111;
  `useSetScores` 141-192; draft transitions 194-258 → reducer in
  `pointDraft.ts`; hotkeys 272-313 → `usePointHotkeys`; `NewServeForm`
  342-373; JSX setup 377-440, palette 441-609, live row 610-648, ledger
  649-688.
- **TournamentSection.tsx (603):** already in-file components → file split:
  draft↔payload 25-140 → `tournamentDraft.ts`; `EntryRow` 144-227,
  `TournamentForm` 228-433, `TournamentCard` 434-511, section 512-603.
  `RANKS` A–I (20) disagrees with `shared/rank.rankOf` (tops at H).
- **match-stats/index.tsx (582):** derivations 107-202 → `profileDerive.ts`;
  `KpiRow` 255-330; `MatchListCard` 331-399; `NewOpponentsCard` 401-443;
  `H2HCard` 457-566 with the IIFE 483-564 → `H2HCard` + `DoublesH2HGroup`.
  27 non-null assertions (`o!.`/`data!.` 263-325, 468-488).
- **database/index.tsx (529):** `RankChip` 17-21 duplicates `PointsChip`
  (`PlayerPicker.tsx:9-18`) → `shared/ui/RankChip`; `PlayerRow` 29-260 → own
  file; sort config 261-267/321; add form 350-371 + 408-473 → `NewPlayerForm`.
- **journal/index.tsx (406):** formatters 23-38; `usePagedDays` 55-80;
  `JournalComposer` 98-168 + 200-375; `Timeline` 377-402.
- **tactics/index.tsx (390):** `usePolling` 56-73; range preset 91-100 (=
  `match-stats/index.tsx:42-46`, `daily-tracker/index.tsx:31-34`) →
  `useRangePreset`; `useFacts` 125-154; `useInterview` 156-198; `H2HTiles`
  246-302.
- **daily-tracker/index.tsx (367):** `useTrackerMutations` 90-194; download
  195-219; editor dispatch on `category.type` 288-352 → `CellEditorModal`.

### 5.4 Dead / stale

- Dead API methods + CSS: see §2.
- Legacy types/fields: `CategoryType "session_note"` (`daily-tracker/types.ts:10-12`),
  `physical_checks` (189), head-coach `video`/`tactics` (`head-coach/types.ts:110-113`),
  `PlayerLevel` "being retired" (`database/types.ts:7`),
  `Match.is_nonplaying`/`nonplaying_label` only render old rows
  (`MatchEditor.tsx:149-150`).
- Stale comments: `MatchRowList.tsx:3-4`, `match-stats/api.ts:13-14`,
  `match-stats/index.tsx:94,445-447,570`, `registry.ts:32-34`,
  `TrainingCenterCard.tsx:2`, `TrainingDisciplineCard.tsx:2`.
- `ComingSoon` is live (used by the one `enabled: false` tab).

### 5.5 Duplication

- Hand-rolled `useEffect` + `alive` loaders remain in
  `daily-tracker/index.tsx:75-86`, `MatchEditor.tsx:337-351`,
  `PlayerPicker.tsx:49-64`, `head-coach/index.tsx:~90-103`, `DevLogs.tsx:20-34`
  (`useLoad`/`useMutate` used in 21 files otherwise).
- 3-second polling loop ×5: `tactics/index.tsx:56-60`,
  `head-coach/index.tsx:109-127`, `CoachChat.tsx:60-71`, `CoachRecaps.tsx:133`,
  `DevLogs.tsx:29` → `usePolling(fn, ms, enabled)`.
- `e instanceof Error ? e.message : String(e)` ×4 (`DurationEditor.tsx:97`,
  `PlayerPicker.tsx:90,111`, `SyncButton.tsx:98`) → export `errMsg`
  (`useApi.ts:12`); PlayerPicker runs its own busy/error; `head-coach/index.tsx:122`
  fakes an error via `run(() => Promise.reject(...))` because `useMutate`
  has no `setError`.
- Match-row rendering ×5: `MatchRowList`, `MatchLines`,
  `match-stats/index.tsx:351-397`, `MatchEditor.tsx:631-701`,
  `MatchLogSection`. W/L class logic repeated (`MatchRowList.tsx:47`,
  `PlayerMatchesModal.tsx:41`, `EloSection.tsx:122,199`,
  `match-stats/index.tsx:373`); W-L-T text (`match-stats/index.tsx:274,428,505`,
  `tactics/index.tsx:263`) → `ResultBadge` + `formatRecord`.
  `tactics/index.tsx:270` own percent instead of `shared/format.pct`.
- Points range 0–3000 hard-coded in `rank.ts:30`, `PlayerPicker.tsx:238,247`,
  `database/index.tsx:149,444,466` → `POINTS_MAX`.

### 5.6 Smells

- Non-null assertions: 27 in match-stats/index.tsx; `EloCurve.tsx:74`,
  `SortableTh.tsx:31`, `PointCharter.tsx:345`, `ExerciseImage.tsx:15`.
- Effects: event-search effect (`MatchEditor.tsx:316-331`) has no stale
  response guard; content-signature deps + lint-disable
  (`MatchEditor.tsx:243-254,279-293`); timers not cleared on unmount
  (`database/index.tsx:68,102`, `PlayerPicker.tsx:168`, `SearchPicker.tsx:113`);
  `PointCharter.tsx:273-313` re-binds keydown on every draft change.
- Magic values: `level: "equal"` placeholder (`MatchEditor.tsx:234,395`);
  debounce 150/180/200 ms; `POINTS_PRESETS` (`TournamentSection.tsx:81`),
  `PAGE = 30` (`journal/index.tsx:21`), gutter 210 (`daily-tracker/index.tsx:43`).
- Prop drilling: `MatchEditor` 7 callbacks via daily-tracker index;
  `PointCharter` 9 props.

### 5.7 Tooling

- No ESLint; 9 inert `eslint-disable` (`useApi.ts:54`,
  `MatchEditor.tsx:253,286,350`, `PointCharter.tsx:312`, `tactics/index.tsx:70`,
  `WorkoutPlayer.tsx:135,147,154`). → eslint + `react-hooks` +
  `@typescript-eslint` (`no-non-null-assertion`: warn) + `lint` script.
- tsconfig already `strict`, `noUnusedLocals/Parameters`,
  `noFallthroughCasesInSwitch`; `noUncheckedIndexedAccess` later maybe;
  `exactOptionalPropertyTypes` — skip.
- No test runner → vitest once pure modules exist (`pointRules`,
  `profileDerive`, handicap math, `tournamentDraft`).

## 6. Plan — phases, one commit each, tests green, affected tabs screenshotted

**Phase 0 — safety net (before any file split)**
- Golden tests: `build_week` cells + CSV export (tracker).
- Characterization tests: `_bundle_to_text`, `_recap_bundle_to_text`.
- ESLint + `lint` script; vitest scaffold.

**Phase 1 — low-risk cleanup**
- Delete the 7 dead tactics API methods, `.tac-reflect*`/`.ml-*`/thumb-ph
  CSS, the backend `/reflections` routes (+ `run_me_extraction_job` if
  nothing else calls it) — keep the table and rows.
- 2 unused imports; `_ensure_activity_unique_index` commit-every-start;
  `open_session` always-False return; package-math no-ops; `rpe == "hard"`
  no-op; `export_xlsx` shadowing; `zip(strict=)`.
- Delete `backend/scripts/imports/*` and `backend/scripts/migrations/*`
  (in git history; they clear tracker rows).
- Fix the ~15 stale comments listed above.

**Phase 2 — backend shared layer**
- `app/shared/`: `ollama.py`, `jobs.py` (`run_llm_job` replaces 5 copies +
  one stuck-job recovery), `persona.py`, `format_vi.py`, `time.py`; tactics
  stops importing head_coach privates (move the test patch targets).
- Typed `NotFound` / `Conflict` exceptions + one FastAPI handler; routers
  stop mapping ValueError by hand.
- `tracker/constants.py` for disciplines + rounds (5 places).
- Explicit `on_startup` hooks in the registry (job recovery out of "migrate").

**Phase 3 — split the god files (facade re-exports keep callers working)**
- `tracker/service/` (13 modules, §3.1), then move router business logic
  (`upsert_activity`, `create/update_match`, …) into it; dedupe the
  coach-session and package-coach lookups, the W/L tallies, the date ranges.
- `head_coach/service/` (§4.2) with ONE section renderer for verdict/recap.
- `training/program/` (§4.2); `program.cycle_for`, `count_done`.

**Phase 4 — frontend**
- Move cross-tab domain types + `MatchRowList` + `RangePicker` to `shared/`.
- `usePolling`, `useRangePreset`, `errMsg`, `ResultBadge` + `formatRecord`,
  `RankChip`, `NewPlayerForm`, `POINTS_MAX`.
- Alias types to `schema.d.ts` one tab at a time; type `round` properly.
- Split match-stats index, TournamentSection, database index, journal index,
  tactics index.
- `useComboOpen` + `ComboList`; PlayerPicker rebuilt on SearchPicker; event
  autocomplete on it too.
- Last: MatchEditor and PointCharter, after `pointRules`, handicap math and
  `tournamentDraft` have vitest coverage.

**Deliberately NOT doing:** `_VI` renames; `exactOptionalPropertyTypes`;
moving tournament placement out of rating.py; ruff E501 reflow; dropping any
column or row (never-delete rule).

**Suspected bugs to test first (Phase 0 or 1):** GET `/today` and the
coach bundle write training rows (also in SHARE_MODE); daily-item
substitution undone by `_ensure_daily`.

Suggested cadence: Phase 0 + 1 in one session, then use the app for a few
days before Phase 2. Rough effort: 0+1 ≈ one evening, 2+3 ≈ two evenings,
4 ≈ two to three evenings.
