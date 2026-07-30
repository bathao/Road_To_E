# Progress Log — Road To E (formerly "Table Tennis Coach", renamed 2026-07-25)

## Current status (2026-07-31, latest) — Tournament link + placement bonus committed `0c043d9`

> **Placement bonus mechanic (user table 2026-07-31, committed `0c043d9`
> together with the 07-30 tournament-link batch below; needs start.bat
> restart):** a final tournament result pays a FLAT ELO add-on —
> no K, no expected score. The placement is NEVER input — first draft had
> a Result picker on the entry row; user rejected it same-day ("dựa vào
> data tôi nhập của giải trong sheet") → fully derived, nothing stored.
>   - **Table (rating.TOURNAMENT_BONUS):** singles 70/50/35 + 10 for
>     reaching-QF-only; doubles 35/25/10; team 30/20/10 (champion /
>     runner-up / third). "third" = LOST THE SF — all bronze is shared, no
>     3rd-place match (user 2026-07-31); "quarterfinal" tier exists ONLY
>     for singles (0 elsewhere).
>   - **Derivation (rating.derive_placements):** group linked matches
>     (tournament_entry_id) per entry, take the DEEPEST entered round's
>     last match: F won → champion · F lost → runner-up · SF lost → third
>     · QF lost → quarterfinal · group-only/shallower → none. 0-0 rows
>     ignored. The ENTRY's discipline prices the bonus (doubles final =
>     +35 even though the rubber rows are stored per-match).
>   - **Missing-data warning (rating.derive_warnings):** tournaments are
>     entered AFTER they finish (user 2026-07-31) → a WON knockout round
>     with no later round means forgotten matches, not an ongoing event.
>     EntryOut.data_warning ("Won the Semi-final but no Final match
>     entered — matches missing?") → red entry chip "⚠ …" on the
>     tournament card; resolves itself once the missing round is entered.
>     Group-only data never warns (group exit is on points, not one loss).
>   - **Replay integration:** the bonus is a STEP in the replay timeline
>     at the END of the deciding match's day (after that day's matches) —
>     editing/deleting matches self-corrects; pre-anchor never pays.
>     ReplayStep.match_id is now `int | None` (None = bonus, +
>     bonus_label/bonus_discipline). counted_matches / breakdown.counted /
>     bucket.counted count MATCHES ONLY; total_delta + curve include it.
>   - **No schema change** (final_placement column reverted before commit;
>     no migration needed). EntryOut echoes DERIVED final_placement +
>     bonus_points.
>   - **GUI:** tournament cards show "🥇 Champion +70" inside the entry
>     chip (tooltip: derived from entered matches); Profile "ELO per
>     match" renders bonus rows gold (🏆 label, no W/L), sorts handle
>     match_id=null (end-of-day order, name = bonus_label).
>   - **Known caveat (accepted):** TEAM events derive from MY last rubber
>     of the deepest round — a tie's team result can differ from my rubber
>     result. Revisit when the first real team tournament exists.
>   - 76/76 pytest (test_tournament_bonus.py ×7), gen:api + build clean.

## Earlier (2026-07-30) — Match ↔ Tournament link + rounds (committed `0c043d9`)

> **Tournament link built (user request + plan OK'd 2026-07-30, committed
> `0c043d9` with the placement bonus above):** tournament matches in the
> grid now know WHICH tournament/entry they belong to and WHAT round.
>   - **Data:** Match gains `tournament_entry_id` (FK tournament_entry;
>     ALTER-added → no SQLite constraint, display tolerates a deleted
>     entry) + `round` ("group"|"r64"|"r32"|"r16"|"r8"|"qf"|"sf"|"f",
>     validated in MatchIn). Migration via add_missing_columns —
>     smoke-tested on a real-DB copy (262 matches intact). MatchOut adds
>     round + tournament_name; MatchLine (h2h) adds round.
>   - **Auto-event:** a linked match with no explicit Event gets the
>     tournament's name as its Event → every existing event-chip display
>     (h2h, modals, coach) labels tournament matches for free.
>   - **Grid:** Tournament-row cells on days a tournament runs get a gold
>     highlight + 🏆 hint when empty + tooltip "enter this tournament's
>     matches here" (FE computes from the already-loaded tournaments list
>     — no new API). Cell text: group-stage keeps compact W(a,b) grouping,
>     knockout rounds each get their own line "QF: W(3-1)" (also in CSV).
>   - **MatchEditor tournament mode:** banner "🏆 giải · hạng" (+ entry
>     dropdown when several entries/tournaments that day); DOUBLES entry
>     locks discipline + pre-fills the registered partner (editable per
>     match) so only opponents get picked; Round dropdown (Group default,
>     smart-defaults to the cell's latest round); Event box pre-filled
>     with the tournament name; round chips on the cell's match list.
>   - Round chips also on MatchRowList (Analysis + Database modals) and
>     MatchLines (Profile h2h). ROUND_LABEL/ROUND_SHORT live in
>     shared/matches.ts; backend ROUND_SHORT in tracker/service.py.
>   - Out of scope (deliberate): bracket view in the Tournament section
>     (wait for the first real tournament's data), coach reading rounds.
>   - 69/69 pytest (new test_tournament_link.py), gen:api + build clean.

## Earlier same day (2026-07-30) — review + cleanup committed `a46ddc0`

> **2-agent review of cfd65cf+bfc1e09, all accepted findings applied
> (committed `a46ddc0`; backend touched → restart start.bat):**
>   - **Real bugs fixed:** Database count badges included NONPLAYING rows
>     while the drill-down modal excluded them (badge ≠ modal rows; count
>     query now filters is_nonplaying, regression assert added).
>     `.tc-grid` CSS class COLLIDED between TrendChart (SVG stroke) and
>     Training Center's DayGrid (display:grid) → TrendChart namespace
>     renamed `tc-*` → `trend-*`. TrendChart reserved phantom loss space
>     when a range had zero losses (Math.max(1,…) floor dropped). ELO
>     table date-sort tiebreak ignored direction. PlayerMatchesModal kept
>     a stale W/L pick when switching roles. Database vs/with sorts had
>     no tiebreak; empty-pool message said 'No one matches ""'.
>   - **Coach bundle waste cut (movers/form it never read):**
>     build_match_stats gained `form_seed=` (coach passes False — skips 4
>     pre-range seed queries/bundle), build_rating_breakdown gained
>     `with_movers=` (coach False — skips per-match row building).
>     Verified NOT a context leak — the bundle serializes only summaries.
>     Movers batch-load switched from unbounded `IN(id…)` to a date-window
>     query (SQLite 999-var limit). `_prior_form_results` skips the 4
>     eager-loads (only scores read).
>   - **Dedup:** backend `_playing_matches(db, with_relations=)` +
>     `_NEWEST_FIRST` (was 3-5 copies); FE `shared/ui/Seg.tsx` (5 seg
>     groups now one component), `matchupOf` → `shared/matches.ts`,
>     `ResultFilter` → shared/types, MatchRowList uses fmtDelta,
>     TrainingCenterCard reuses DAY_ICON; `_h2h_accumulate` computes lvl
>     for singles only.
>   - **Dead CSS deleted:** .va-tab/.va-card* (only .va-muted lives),
>     .db-chart, the old .db-me* (renamed → .prof-elo* in profile.css);
>     cross-tab .smm-* + .elo-chip/head/current moved daily-tracker.css →
>     base.css; TrendChart keys now bucket-stable; stale comments swept
>     (top_gains, profileApi, "Match Stats tab" → Profile, BarChart…).
>   - **Declined (deliberate):** EloHeader extraction (two headers already
>     diverged twice — coupling loses), per-role param on
>     players/{id}/matches (FE filters client-side, counts consistent
>     after the nonplaying fix), row cap on the drill-down (local tool,
>     tiny data), form carry-forward across quiet buckets (by design —
>     FE only renders played buckets).
>   - 67/67 pytest, gen:api + build clean.

## Earlier same day (2026-07-30) — Profile merged into Match Stats → tab "Profile" 🪪 (committed `bfc1e09`)

> **Committed as `bfc1e09`** ("commit code đi", second batch of
> 2026-07-30): tab merge + read-only header + avatar + ELO per-match
> sortable table + 2×2 layout + shared SortableTh + default Month.
> Net −110 lines. Nothing uncommitted; restart start.bat if not done
> since the movers API change.

> **Tabs merged (user decision 2026-07-30, "Giải thể Profile" + layout
> "General info trên, match stat giữa, training dưới", UNCOMMITTED,
> FE-only — F5):** the standalone Profile tab is GONE; the Match Stats tab
> absorbed its unique pieces and was RENAMED "Profile" 🪪 (folder stays
> tabs/match-stats, registry id unchanged). Page order: (1)
> GeneralInfoCard — avatar (user photo copied root "Nguyễn Bá Thảo.jpg" →
> frontend/public/avatar.jpg, git-tracked; public-db-ok), name, CURRENT
> ELO big number + "X to E" chip + anchor Edit (same no-op-save guard;
> saving bumps a reloadSignal that refetches match-stats + breakdown),
> "Data as of"; (2) PeriodControl + filters → KPIs → charts row → lookup
> row (unchanged); (3) training row: TrainingDisciplineCard (now follows
> the PeriodControl instead of the old 30/90/365/all picker — "All" is
> gone, use Custom) + TrainingCenterCard (rangeless). Deleted:
> tabs/profile/* (incl. MyRatingCard — its private ELO curve + period
> picker died, the page's ELO card covers it; CompetitiveCard — the KPIs
> cover it), profile.css slimmed to prof-header/avatar/name/asof/cat-list.
> getMyRating/lastDate/trainingStats moved into matchStatsApi;
> MyRating/TrackerStats types into match-stats/types. Backend untouched.
> Follow-up (user: "Không cho cơ chế edit luôn... Tôi chỉ có thể tăng giảm
> được điểm qua các trận đánh"): the anchor Edit UI was REMOVED entirely —
> the header is read-only, setMyRating dropped from the FE api (PUT
> /tracker/my-rating stays server-side for a deliberate manual re-anchor),
> and the reloadSignal wiring went with it. The root photo "Nguyễn Bá
> Thảo.jpg" was also MOVED (not just copied) into frontend/public/ — repo
> root is clean. Build clean.

## Earlier same day (2026-07-30) — Match Stats 2×2 layout + ELO table block (uncommitted)

> **Match Stats layout rework (user: "nhìn khá lôm côm", same day,
> UNCOMMITTED, needs start.bat restart):** the tab is now KPIs → charts row
> (Results & form | ELO over time curve) → lookup row (ELO per match |
> Head-to-head), all in the shared .stats-cols grid — the ELO table got its
> OWN card ("tách riêng block") with a 480px scrollable body so many more
> rows show. Its **default sort is now Date, newest first** (user request;
> the API's movers order flipped to newest-first to match — test updated).
> EloSection.tsx now exports EloCurveCard + EloTableCard (no more single
> full-width section; .elo-section/.elo-cols CSS replaced by .elo-note*).
> The long "computed over ALL ELO-counted matches" endnote became a short
> muted line under the curve card's header. ELO cards still render when
> the filtered match list is empty (rating is global). Follow-up (user:
> "đôi phải hiện đủ tôi đứng với ai, bên kia là ai vs ai"): the Match
> column now shows the FULL line-up for team formats — RatingMoverOut
> gained opponent2_name/partner_name, and the "with P vs A + B" wording
> was extracted from MatchRowList as the structurally-typed `matchupOf()`
> and reused, so the table and both drill-down modals share one phrasing.
> 67/67 pytest, gen:api + build clean.

> **Match Stats "Biggest movers" → "ELO per match" sortable table (user
> request 2026-07-30, built same day, UNCOMMITTED, needs start.bat
> restart):** the top-3-gains+top-3-losses list became a 4-column table —
> Date | Match ("3-0 vs X (Singles)") | W/L | ±ELO — with clickable sort
> headers like the Database tab (Date newest-first, Match by opponent
> A→Z, W/L wins-first, ±ELO gains-first / reversed = biggest losses; no
> active sort = |Δ| desc, the old movers order). Sorting needs full data,
> so the API now returns EVERY counted match in range:
> MyRatingBreakdownOut.top_gains/top_losses REPLACED by `movers`
> (batch-loaded matches, no more per-row db.get). The header component was
> EXTRACTED to shared/ui/SortableTh.tsx (+ generic toggleSort helper;
> .th-sort/.sort-arrow CSS moved database.css → base.css) and the Database
> tab now uses it too. Table scrolls at ~262px with a sticky header;
> .elo-mover* CSS replaced by .elo-table*. 67/67 pytest, gen:api + build
> clean.

## Earlier same day (2026-07-30) — batch committed `cfd65cf`

> **The whole 2026-07-29..30 batch is COMMITTED as `cfd65cf`** (one code
> commit, "commit code đi" 2026-07-30): (1) "+ Add player" form, (2) Match
> Stats ELO curve replacing delta bars, (3) movers |Δ| sort, (4) level
> chart removed from Match Stats, (5) per-level cards removed from
> Profile, (6) by_level removed from the API, (7) "Results & form" trend
> chart (KEPT after the revert wobble — see entry below), (8) Database
> per-player match drill-down. 67/67 pytest, gen:api + build clean.
> Backend changed (form field, by_level removal, players/{id}/matches) →
> restart start.bat if not done since. No other open thread; next work is
> the data-blocked TODO list.

> **Database tab: per-player match drill-down (user request 2026-07-30,
> built same day after plan OK, UNCOMMITTED, needs start.bat restart):**
> the "⚔️ Vs me" / "🤝 With me" counts are now buttons → modal listing every
> match with that player (all-time — the tab has no period control), same
> match lines as the Daily Tracker Analysis drill-down. New endpoint
> `GET /tracker/players/{id}/matches` (service.list_player_matches: any
> slot — opponent/opponent2/partner — nonplaying excluded, newest first,
> `_annotate_elo`'d so each row carries its ±ELO chip). The row rendering
> was EXTRACTED from StatMatchesModal into shared
> daily-tracker/components/MatchRowList.tsx (namesOf/hdcText/kind labels)
> — both modals now render identical lines by construction. New
> database/PlayerMatchesModal.tsx: role seg All/⚔️Vs/🤝With (only shown
> when the player has BOTH roles; preset by which count was clicked) + the
> usual All/W/L seg. CSS: .db-count-btn link-style counts, .pm-filters.
> 67/67 pytest (new any-slot/ordering test), gen:api + build clean.

> **"Win rate trend" chart: redesign kept after a wobble (2026-07-30):**
> user first said the new "Results & form" chart was worse than the old
> line once they realized 0% days were real losses — a revert was started —
> then reconsidered mid-revert ("à thôi hiểu rồi, giữ cái hiện tại cũng
> dc", "giữ results and form"). The revert was undone; the shipped state is
> the NEW chart (verified byte-identical bundle to the pre-revert build).
> Details in the entry below.

> **"Win rate trend (by day)" chart REDESIGNED (user: "nhìn line chart xấu
> quá", same day, UNCOMMITTED, needs start.bat restart):** the per-day
> win-rate LINE was statistical noise at 2-3 matches/day (0%↔67% spikes;
> a 0% day with 1 loss looked like a day with 8). NOTE: the 0% points the
> user read as "days not played" were actually played-and-lost-all days —
> non-played days were already filtered out. New chart "Results & form":
> **W/L bars** (wins green up, losses red down from a shared baseline,
> equal counts = equal heights — the only honest per-day signal) + a
> **rolling-form line** = win rate of the last 10 DECIDED matches (right
> 0-100% axis; ties skipped; hidden until 3 decided matches). Backend:
> MatchTrendBucket gains `form`; `_trend_buckets` threads a deque window,
> seeded by `_prior_form_results` (last 10 decided named matches BEFORE
> date_from, floor-respecting, same discipline/category filters) so the
> line doesn't restart at the range edge. FE: new
> match-stats/components/TrendChart.tsx replaces LineChart in the tab
> (LineChart itself still serves other tabs); tc-* CSS in match-stats.css;
> tooltip reuses .lc-tooltip and shows "W-L[-T] · n matches" + form.
> Chosen over per-day % alternatives on the user's "tự chọn như chuyên gia
> thống kê" mandate. 66/66 pytest (new rolling-form test), gen:api + build
> clean.

> **"Win rate by opponent level" bars REMOVED from Match Stats (user:
> "có điểm rồi vô nghĩa", same day, UNCOMMITTED):** the dynamic ELO already
> prices opponent strength, so the below/equal/above split told the user
> nothing. LevelBars.tsx deleted + its lvl-* CSS (match-stats.css) and
> .lvl-fill.level-* (base.css). Follow-up "bỏ luôn đi": the Profile tab's
> per-level cards went too — CompetitiveCard now shows the overall card
> only; MatchStatsLite dropped by_level. Second follow-up "bỏ API luôn
> đi": **by_level REMOVED from MatchStatsResponse entirely** —
> schemas.LevelRecord deleted, _h2h_accumulate no longer tallies per level
> (the derived at-match-time level still labels h2h records), and the
> coach bundle/context lost its "Theo hạng đối thủ" line. The coach KEEPS
> by_level_handicap (level × chấp split — still per-level context) + the
> ELO trend. head-coach FE SourceMatchDetail.by_level? stays optional so
> pre-removal snapshots still type-check. 65/65 pytest, gen:api + build
> clean. Restart start.bat (backend change). (.level-chip.level-* rules
> are separate and still live — h2h pair labels use them.)

> **Match Stats ELO redesign (user: "nhìn ko hiểu", fixed same day,
> UNCOMMITTED, FE-only — F5):** the center-zero signed delta BARS ("Δ by
> day") were the one ELO visual unlike everywhere else — replaced with the
> shared EloCurve (same line as Daily Tracker + Profile; per-bucket Δ and
> match counts live in its hover tooltip). "Biggest movers" column kept.
> Dead .elo-delta-rows/row/label/track/fill CSS removed (.elo-delta-val
> pos/neg kept — the movers list uses it). Follow-up (user: "phải có cái
> bị trừ lớn nhất chứ"): the losses WERE there, but gains-then-losses
> ordering hid them (a +2.2 above a −3.6) — movers now render as ONE list
> sorted by |Δ| desc, so the biggest deduction ranks right where its
> impact puts it.

> **"+ Add player" on the Database tab (user request, built same day,
> UNCOMMITTED, FE-only — F5):** toolbar button toggles an inline dashed
> form (Name + Points with live RankChip — empty = unrated — + pips
> checkbox; Enter = create, Esc = close). Calls the existing POST
> /tracker/players (get-or-create by name, so re-adding an existing player
> harmlessly returns the existing row), then reload()s the list (counts +
> ordering are server-side). databaseApi gained createPlayer.

## Earlier same day (2026-07-29) — ELO readability, committed `d17b5ed`; ALL PUSHED

> **Committed `d17b5ed`** + this PROGRESS right after, then PUSHED the whole
> backlog to origin/master (was ~84 commits ahead). Tree clean.
>
> **ELO chart readability (user report: "nhìn vào không thấy điểm Elo là
> bao nhiêu liền", fixed same day):** user picked the title approach over
> on-chart point labels — the rating at the range's end now renders as a
> BIG bold number right after "📈 ELO" (new .elo-current, daily-tracker.css)
> in the Daily Tracker EloBlock AND Match Stats EloSection; the small
> endnote shrank to "from <start>" (+ the filter-independence disclaimer on
> Match Stats). Follow-up ("font chữ hover thô quá"): .lc-tooltip toned
> down — value 22px accent-blue → 13.5px dark semibold tabular-nums, date
> 11.5px muted, tighter padding/softer shadow, matching the comparison
> chart's ac-tooltip scale (all 3 LineChart users benefit).
> Also recorded: entry speedups DROPPED by user ("ko làm"), Motivation tab
> waits for the user's signal, Profile range-picker unification rejected —
> never re-suggest any of these (memory/dropped-ideas.md + TODO.md).

> **Committed `14e977d`** (all three same-day Database-tab features below) +
> this PROGRESS right after; tree clean; 65/65 pytest; build + gen:api
> clean. **Restart start.bat once** (backend: rename duplicate-guard +
> matches_vs/matches_with counts; then F5).
>
> **Matches column split ⚔️/🤝 (user request, built same day):** the single "Matches"
> count mixed opponents with partners ("khó nhận biết"). PlayerDbRow now
> carries `matches_vs` (opponent OR opponent2 slot) + `matches_with`
> (partner slot) — `matches_played` REMOVED (Database tab is the only
> consumer; gen:api regenerated). FE shows two sortable columns "⚔️ Vs me"
> / "🤝 With me" (0 renders as "—"); SortKey matches → vs|with. Test
> updated to assert the split counts. 65/65 pytest, build clean.

> **Column sorting (user request, built same day):** Name / Points / Matches headers
> are clickable — first click sorts by that column's most useful direction
> (name A→Z with `localeCompare("vi")`, points high→low, matches many→few),
> second click reverses; active column shows ▲/▼, inactive a faint ↕.
> Unrated players sink to the bottom in BOTH points directions. Level column
> deliberately not sortable (it derives from points). Initial state stays
> the server order (rated by points desc, unrated last) until a header is
> clicked. Components: SortableTh + SORT_DEFAULT_DIR in database/index.tsx.

> **Player rename (user request, built same day).** Some players were
> entered before the user knew their real name; now they can be fixed
> in place.
>   - **FE (Database tab):** hover a row → ✏️ button on the name → inline
>     input (Enter/blur = save, Esc = cancel, autoFocus); reuses the row's
>     ✓/✕ flash. On failure (e.g. duplicate) the editor STAYS OPEN with the
>     draft so the user can adjust; the error banner explains why.
>   - **History follows automatically by design** — matches store player
>     IDs; names are resolved at read time (grid, h2h, coach bundle, ELO
>     movers), so no data migration of any kind.
>   - **Backend guard (user picked "chặn trùng tên"):** update_player now
>     rejects renaming INTO another player's name (case-insensitive) with
>     ValueError → router 400 — two identical rows would be
>     indistinguishable in the picker; a true "same person twice" case
>     needs a MERGE feature (explicitly deferred until it actually happens).
>     Creates were already safe (create_or_get_player dedupes by name).
>   - **Verified:** 65/65 pytest (new
>     test_player_rename_updates_history_and_blocks_duplicates: rename →
>     build_week shows the new opponent name; duplicate rename raises;
>     self-rename no-op), npm build clean.

## Earlier same day (2026-07-29) — PROJECT-WIDE CLEANUP, committed `8e7b023`

> **Resume next session.** The full review→cleanup batch is BUILT, VERIFIED
> (64/64 pytest, app imports, npm build + gen:api clean) and committed
> `8e7b023` (+ this PROGRESS right after). **Restart start.bat once** (the
> running backend still mounts /api/video and the old code). User decisions
> this batch: delete video_analysis ENTIRELY (not just the dead half);
> untrack roi_seg.pt but KEEP the 190 MB identity photos on disk; do ALL the
> big refactors; rewrite TODO.md fully.
>
> **VIDEO_ANALYSIS FEATURE DELETED (user decision, escalated from "delete
> the dead half"):**
>   - Backend app/features/video_analysis/ REMOVED (router/service/schemas/
>     models/text_synth/seed + TEXT_ANALYSIS_PLAN.md). All va_* TABLES + ROWS
>     KEPT in SQLite (user data is never deleted) — they are simply
>     unreferenced now. registry.py NOTE documents this.
>   - head_coach still needs ONLY the player's name → new _player_name(db)
>     reads va_profile.name via raw SQL with a fallback (no models import).
>   - training prescription_for + _apply_prescription DELETED (they injected
>     exercises from the retired va_skill ratings — this also RESOLVES the
>     old "prescription_for product decision"). is_prescribed/rx_reason
>     columns + FE badge kept for historical rows; TrainingSession.adapted
>     is now frozen (comment on the model).
>   - FE tabs/profile/engine/ + SkillRadar DELETED; Profile tab rebuilt:
>     header + MyRatingCard + range pills + 3 extracted cards
>     (CompetitiveCard / TrainingDisciplineCard / TrainingCenterCard), all
>     loads via useLoad. video-analysis.css deleted (all its classes were
>     engine-only); the 4 surviving va-* classes (va-tab/card/card-head/
>     muted) live in base.css relabelled "generic card layout"; profile.css
>     trimmed of radar/skill-bar rules; dead pb-*/db-me-label rules purged.
>   - SourceSummary.video/tactics legacy shims KEPT (old snapshots parse).
>
> **BEHAVIOUR FIXES:**
>   - Coach bundle: 7 full ELO replays per call → ONE. rating.replay result
>     (new ReplayResult alias) threads through build_match_stats /
>     build_handicap_split / build_rating_breakdown / compute_my_rating via
>     an optional replay= param; gather_bundle replays once. Matters because
>     the bundle runs on EVERY chat message.
>   - Mixed-language coach grounding: training summary_vi (English GUI
>     prose) is no longer injected into the Vietnamese prompt — the raw
>     numbers were already in the bundle; the "Tự nhận xét tuần" line is
>     gone. GUI keeps the English summary.
>   - 5 one-shot scripts (4 imports + add_coach_package_marker) crashed if
>     re-run (ModuleNotFoundError: app) — the 3-line sys.path shim from
>     add_match_opponents.py is now in all of them.
>   - match-stats: setSelOpp("") ran INSIDE the useLoad fetcher → moved to a
>     proper useEffect.
>
> **REFACTORS (behaviour-preserving, all tests/builds green):**
>   - tracker/service.py: _annotate_elo() (the byte-identical ELO annotation
>     loop from build_week + list_stats_matches); _coach_sessions() (the 3×
>     coach-session query); build_match_stats 236 lines → _query_named_
>     matches + _h2h_accumulate + _record_tail (shared OpponentRecord/
>     DoublesRecord tail) + _trend_buckets + ~70-line assembler; dead
>     STATS_BUCKETS + rating.deltas_by_match deleted; the mid-file rating
>     import shim moved to the top imports (kept — router/tests use it).
>   - head_coach/service.py: gather_bundle 142 lines → _training_summary +
>     _match_summary + _match_detail; _ollama_chat() owns the payload/
>     timeout/num_ctx for both _call_model + _call_chat_model;
>     _call_with_empty_retry() the shared retry-once; dead sync generate()
>     deleted; _to_out uses _tz; MIN_SAMPLE_MATCHES → private.
>   - FE shared/: new disciplines.ts (DISCIPLINES/LABEL/SHORT — replaces 5
>     copies; Discipline type moved here, daily-tracker re-exports),
>     resultOf() in types.ts (replaces 3 copies incl. one that dropped the
>     tie case), shortDate/dmyDate in dates.ts, fmtDelta in format.ts,
>     LevelRecord/CategoryMinutes promoted to shared/types.ts, new
>     ui/EloCurve.tsx = THE one since-anchor curve engine (AnalysisPanel
>     EloBlock + MyRatingCard RatingChart are now thin wrappers).
>   - AnalysisPanel: MatchCard + CoachPackageCard extracted to components/;
>     hand-rolled seq/alive loaders → useLoad/useMutate (440 → ~300 lines).
>   - Error-handling REVIEWED, deliberately left: ValueError→400 (tracker
>     business rule) / 404 (training bad path resource) / 409 (chat pending)
>     are each locally correct; the blanket except→502 died with the video
>     router.
>   - NOT unified on purpose: the Profile tab's 30/90/365/all pills vs
>     MyRatingCard's PeriodControl (two range models on one screen) — a
>     product/UX call, not a refactor; ask the user someday.
>
> **DOCS + HYGIENE:**
>   - README.md rewritten (all 6 tabs, Ollama qwen3.5:9b prerequisite,
>     requirements-dev.txt for pytest). TODO.md rewritten from scratch
>     (open items: mis-anchored report, ETA projection, scale_backtest ~Oct,
>     t=1.5 placeholder, entry speedups, Motivation tab). PLAN.md restamped
>     HISTORICAL + layout-drift warning. PROGRESS.md trailing ## Run block
>     fixed (no Video tab / qwen3-vl / ffmpeg). exercises/README.md: the
>     drifting hand-list replaced by "keys come from program.py".
>     identity/me/README.txt restamped retired (photos = personal data,
>     kept). settings.py TEXT_MODEL comment updated.
>   - .gitignore: +.pytest_cache/, retired-pipeline block collapsed
>     (data/models/ now fully ignored); **roi_seg.pt (6.77 MB) untracked**
>     via git rm --cached, file kept on disk. Stray .pytest_cache dirs +
>     orphaned video_analysis .pyc deleted. index.html lang="vi" → "en".
>     start.bat mediapipe rationale dropped (3.12 pin kept). TournamentStrip
>     stale VN comment fixed.
>   - KEPT deliberately: CoachChat.tsx example prompt “Tôi muốn đánh đơn tốt
>     cho giải 2/8” — it is an example of what the user TYPES TO THE COACH,
>     and the coach conversation is legitimately Vietnamese.
>   - Still outstanding: **76+ commits unpushed** to origin/master (user
>     never asked to push); suggest pushing next session.
>
> Net: −~4.4k lines of code/docs (engine + video_analysis + dedup) across
> ~60 files; behaviour changes limited to the listed fixes. Next candidates
> unchanged: mis-anchored-opponent report + ETA projection (need weeks of
> data); entry speedups; scale_backtest ~Oct.

## Earlier (2026-07-29) — English UI + ELO chart sync + stat drill-down, committed `72a26f2`

> **Resume next session.** Committed `72a26f2` (code + daily DB data) + this
> PROGRESS right after; tree clean; 64/64 pytest; build + gen:api clean.
> **Restart start.bat once** — new backend pieces: /stats/matches endpoint,
> anchor_points on /my-rating/breakdown, /my-rating/history REMOVED, English
> training curriculum + unit labels. Next candidates unchanged:
> mis-anchored-opponent report + "Road To E" ETA projection (need weeks of
> data); entry speedups (Copy yesterday / Quick add); re-run scale_backtest.py
> ~Oct; the prescription_for product decision (still open).
>
> **THIS BATCH (2026-07-28..29, user-driven UI iterations):**
>   - **ELO chart sync (Daily Tracker Analysis):** LineChart now supports
>     null-gap segments + an "aligned" slot/gutter mode mirroring
>     ActivityChart, so the ELO line shares the SAME day axis/columns as the
>     comparison chart (and the grid above). Future buckets draw NOTHING on
>     both charts (ActivityPoint.blank / null values); pre-anchor days draw
>     FLAT at the anchor value — new `anchor_points` field on
>     /my-rating/breakdown. Tooltip edge-clamp (.edge-left/.edge-right) fixed
>     the clipped first/last-point tooltip. Also: stat-grid spacing under the
>     ELO card, 1v2/2v1 cards removed (entry + Match Stats filter kept), sets
>     row removed from match cards.
>   - **ENGLISH UI SWEEP (user decision 2026-07-28 — supersedes "VI OK in
>     GUI" from 2026-06-08):** ALL GUI text → English. Vietnamese remains
>     ONLY in (a) the coach conversation — head_coach prompts + AI content,
>     incl. the tournament labels fed into the bundle — and (b) user data.
>     Swept every FE tab (5 parallel agents + manual CSS/comment pass) AND
>     backend user-visible strings: the whole training/program.py curriculum
>     (exercise names, muscle groups, tt_benefit, form-cue safety text,
>     HOW_TO steps), weekly-summary templates, _METRIC_UNIT_VI →
>     sessions/hours/matches, tracker error strings. `*_vi` field NAMES kept
>     (API shape unchanged). memory/language-convention.md updated.
>   - **Profile ELO curve rebuilt on the breakdown engine:** MyRatingCard now
>     calls /my-rating/breakdown (real time axis, carry-forward on quiet
>     days — the old matches-only axis compressed rest gaps) with its OWN
>     PeriodControl timeline: modes Week/Month/Year/Custom (new `modes` prop
>     on the shared PeriodControl; Day omitted — nothing to draw), default
>     Month, ◀ Today ▶ nav, pre-anchor flat + future blank like the tracker.
>     `/my-rating/history` + rating.build_history + MyRatingHistoryOut/
>     RatingPoint DELETED — ONE curve engine (build_rating_breakdown) app-wide.
>     Bugfix mid-build: switching to Week right after a fresh anchor hid the
>     chart AND the selector (single bucket) — header/selector now always
>     render, only the line falls back to a hint.
>   - **Stat-card drill-down (user idea, refined):** click a match card
>     (Singles / Doubles / All matches / vs Pips) → modal listing the exact
>     matches behind the number in the visible range — date, S/D/1v2/2v1 tag,
>     opponents/partner, W/L score (colored), give/receive handicap, kind
>     (casual/light stakes/tournament), event, ±Δ ELO chip; newest first.
>     Clicking the W or L count opens it pre-filtered (All/nW/nL chips
>     inside). New GET /tracker/stats/matches?from&to&bucket= shares its
>     predicate (`_in_stats_bucket`) with build_stats so card numbers and the
>     list can never disagree; ELO-annotated like build_week.
>     test_stats_matches.py asserts list≡card per bucket (incl. vs_pips via
>     opponent2 in doubles), ordering, annotations.
>   - **Verified:** 64/64 pytest, npm build + gen:api clean after every step.

## Earlier (2026-07-27) — coach ELO trend + audit-debt cleanup, committed `335babd`

> **Resume next session.** Committed `335babd` (code) + this PROGRESS right
> after; tree clean; 63/63 pytest; build clean. −935/+253 lines net.
> **Restart start.bat once** (new backend + the one-time tracker_match FK
> rebuild; the daily backup runs first in lifespan). Next candidates:
> mis-anchored-opponent report + "Road To E" ETA projection (both need a
> few weeks of match data); entry speedups (Copy yesterday / Quick add);
> re-run scale_backtest.py ~Oct; the prescription_for decision below.
>
> **COACH LEARNS THE WEEKLY ELO TREND + OLD AUDIT DEBT CLEARED (user picked
> #1 and #6 from the next-steps analysis, built same session).**
>   - **#1 Coach ELO trend:** gather_bundle adds my_elo.weekly (last ~6 week
>     buckets via build_rating_breakdown: delta/counted/rating_end; weeks
>     before the anchor dropped); _elo_line renders "Diễn biến ELO theo TUẦN
>     (cũ → mới): dd/mm–dd/mm: ±Δ (N trận, cuối tuần R) · …". SYSTEM_PROMPT
>     rule: read the DIRECTION of the series, ±20/tuần is luck noise at ~20
>     matches/week, conclude only on 3-4 same-sign weeks, and a losing week
>     full of kèo-trên can still be a good week; CHAT prompt got the short
>     version.
>   - **#6a retired pipeline deleted:** video router /health/model +
>     /reports* endpoints, service list/get/create/parse/delete/review
>     report + report_detail_out + _clamp_date + _clamp01, text_synth
>     extract_findings + check_models, schemas ReportCreateIn/AnalysisReport*
>     /ReviewIn/FindingDecisionIn/ModelHealthOut. va_report table + rows KEPT
>     (build_report still counts reviewed ones for the coach). /api/video
>     prefix kept as historical name.
>   - **#6b FE folder rename:** tabs/video-analysis → tabs/profile/engine
>     (git mv file-by-file — folder-level mv hit Windows permission denied);
>     imports fixed (profile/index, SkillRadar, engine/api shared path).
>     styles/video-analysis.css name kept (classes are va-*).
>   - **#6c FK pragma ON** (core/db.py) + **tracker_match rebuild**: the 3
>     ALTER-added player columns had NO FK in the live table (SQLite can't
>     add FKs via ALTER) — new idempotent seed._rebuild_match_player_fks()
>     rebuilds from the canonical model DDL (create → copy by name → verify
>     count → drop → rename → recreate indexes), aborts untouched on any
>     dangling id or count mismatch. Real-DB copy: 253/253 rows kept,
>     foreign_key_check clean, dangling opponent_id now REJECTED.
>   - **#6d grid dedup:** the ~70-line build_week/_build_grid near-copies
>     (source of the old export-parity bug) merged into ONE renderer
>     service._grid_cells(db, rng, days, for_export=) — export differences
>     (full note text, "Training Center" prefix vs 💪) are explicit flags.
>     Smoke asserts grid ≡ export cell-by-cell for the current week.
>   - **Verified:** 63/63 pytest, build + gen:api clean, smoke on real-DB
>     copy (WAL sidecars copied — see gotcha below). Restart start.bat to
>     load the new backend + run the FK rebuild (backup runs first in
>     lifespan, before seeds).
>   - **Still open (product decision, from the old audit):** training
>     prescription_for still injects exercises from RETIRED va_skill ratings
>     into every new session — contradicts the "no model guesswork" principle;
>     ask the user whether to drop that input.

## Earlier same day (2026-07-27) — 1v2/2v1 + ELO analytics relocation, committed `0c424ac`

> **Committed `0c424ac`** (code for BOTH same-day batches below: 1v2/2v1
> disciplines + PlayerPicker fix + my-rating relocation + breakdown), this
> PROGRESS right after. Tree clean; 63/63 pytest; build clean. Server was
> restarted mid-session and verified on the new stack; restart start.bat
> once more if it predates the breakdown endpoint.

> **MY-RATING MOVED OUT OF DATABASE + ELO-OVER-TIME ANALYTICS (user request
> + plan approved 2026-07-27, built same session, UNCOMMITTED).** User: the
> Database tab is for OTHER people's static points; my dynamic rating
> belongs with progress analysis (Profile / Match Stats / Daily Tracker).
>   - **New endpoint** GET /tracker/my-rating/breakdown?from=&to=&unit=
>     (day|week|month) → per-bucket {delta, counted, rating_end
>     (carry-forward; None pre-anchor)} + total_delta + rating_start/end +
>     top 3 ±Δ movers (opponent, discipline, score). service.
>     build_rating_breakdown over rating.replay steps + _bucket_ranges.
>     GLOBAL by design (v1 decision): no discipline/category filter — a
>     filtered rating_end would lie; filtered deltas = future idea.
>   - **Profile tab**: new MyRatingCard (components/MyRatingCard.tsx) right
>     under the header — big current + "còn X tới E" + anchor-edit ("Sửa",
>     same no-op-resave guard) + since-anchor daily curve. my-rating API
>     calls moved databaseApi → profileApi.
>   - **Database tab**: card + curve + my-rating api/types REMOVED; sub
>     text points to Profile.
>   - **Daily Tracker / AnalysisPanel**: new EloBlock — header chip "Δ ròng ·
>     N trận · (start →) cuối kỳ" + LineChart of rating_end per bucket over
>     the SHARED timeline (chartUnit; unit=day fallback so single-day mode
>     still answers "hôm nay ±bao nhiêu"). Hidden when range predates anchor.
>   - **Match Stats**: new EloSection (components/EloSection.tsx) below the
>     3 analytics cards — KPI chip + signed Δ bars per bucket (center-zero,
>     buckets with counted>0 only) + "Trận ảnh hưởng nhất" (top gains +
>     losses). Deliberately rendered OUTSIDE the hasMatches branch and
>     labeled "không theo 2 bộ lọc phía trên".
>   - **Verified:** 63/63 pytest (breakdown buckets/carry/pre-anchor/movers
>     test), build + gen:api clean; smoke on real-DB copy with today's 8
>     real matches: 950 → 948, net −1.7, top gain +11.6 (thắng Nguyễn Văn
>     Trung, đơn), top loss −3.6 (thua 2v1 với Lợi Phạm).
>   - **GOTCHA (smoke):** the live DB runs WAL — copying tabletennis.db
>     alone yields a STALE schema (the startup ALTER TABLEs sat in -wal);
>     smoke scripts must copy the -wal/-shm sidecars too.
>   - **⚠ RESTART start.bat required** — the FE now calls the new breakdown
>     endpoint from the Analysis panel; on the old backend it 404s and the
>     panel shows an error banner.

## Earlier same day (2026-07-27) — NEW DISCIPLINES 1v2 / 2v1 (uncommitted)

> **1v2 / 2v1 formats added (user request 2026-07-27, built same day,
> UNCOMMITTED).** `one_v_two` = user plays ALONE vs two opponents;
> `two_v_one` = user + partner vs one. A format the user plays often.
>   - **No DB migration:** the existing slots cover both — 1v2 uses
>     opponent+opponent2 (partner NULL), 2v1 uses partner+opponent
>     (opponent2 NULL); snapshots already existed for all three slots.
>   - **ELO rule (user, refined mid-build):** the solo side's ELO "×2" is
>     for the COMPARISON ONLY ("coi như 2 người tôi đánh với 2 người bên
>     kia") — on the team-average scale the solo player stands in as both
>     members, so 1v2: mine = my rating vs (opp1+opp2)/2; 2v1: (me+partner)/2
>     vs opp. **The win/loss Δ keeps the normal magnitude — never doubled**
>     (user corrected an initial sum-scale reading mid-work). Chấp folds "như
>     công thức bình thường": FULL ladder bonus (no doubles-style halving).
>     Skips mirror doubles: 1v2 needs both opponents named+rated, 2v1 needs
>     the partner. Assumes solo-at-R vs pair-avg-R is an even kèo — noted in
>     rating.py to revisit with data if the format proves lopsided.
>   - **Grid/export prefixes** `1v2: W(3-1)` / `2v1: L(1-3)` (D: unchanged);
>     _GROUP_ORDER + _DISCIPLINE_PREFIX in service.py.
>   - **MatchEditor:** seg Singles/Doubles/1v2/2v1; pickers per format
>     (hasPartner/hasOpp2); list tags S/D/1v2/2v1; last-handicap pre-fill
>     stays singles-only.
>   - **Match Stats:** discipline filter gained one_v_two/two_v_one (router
>     regex + FE chips); team-style matchups reuse doubles_h2h with a new
>     `discipline` field, key format now `discipline|partner|opp1-opp2`
>     (so 2v1 vs A never merges with doubles vs A+unnamed); h2h heading
>     shows "Đôi/1v2/2v1 · tôi …".
>   - **StatsResponse** gained one_v_two/two_v_one buckets (they no longer
>     leak into the singles bucket); AnalysisPanel shows 2 new MatchCards.
>   - **Coach:** match_sum + context lines for both formats; SYSTEM_PROMPT +
>     CHAT_SYSTEM_PROMPT rule: 1v2/2v1 are their own formats, never pooled
>     with singles/doubles.
>   - **Verified:** 62/62 pytest (4 new: replay math + skips, 1v2 chấp full
>     value, cell prefixes, match-stats grouping/filter), build + gen:api
>     clean, smoke on a real-DB copy (deltas hand-checked: +2.3 / −9.43).
>   - **NOTE from the smoke:** the LIVE DB still lacks the snapshot columns —
>     start.bat has NOT been restarted since before ELO Phase 1; the smoke
>     script had to run seed.migrate() on its copy. **Restart start.bat** is
>     now doubly required (migration + this feature).
>     → RESTARTED + verified same day: new endpoints live, snap columns
>     migrated, tournament_match seeded, fresh bundle served.
>   - **PlayerPicker bugfix (same day, user report):** the add-new-player
>     points input ("chưa rõ") was unfocusable — the .player-add block's
>     blanket onMouseDown preventDefault (meant to keep the dropdown open)
>     also blocked focusing the input. Now preventDefault only for
>     non-INPUT targets. Bug predates today (since the points-first add
>     flow, 2026-07-25). Rebuilt; reload picks it up.
>   - **Racket time questioned by user (2 h training + 8 matches → 4 h 25):**
>     verified NOT a bug — 29 sets × RACKET_MINUTES_PER_SET (5) = 145 min
>     by design. Offered to recalibrate the constant from real session
>     length; user decided to keep 5 min/set ("thôi vậy cũng dc").

## Earlier (2026-07-27, end of previous session) — Phase 2 + scale 0.5 + labels retired, committed `108d50d`

> **Resume tomorrow.** Everything committed (`108d50d` code, this file
> right after); tree clean; 58/58 pytest; build clean. USER MUST RESTART
> start.bat once — the running server predates today's whole ELO stack
> (tournament_match category, snapshots, /my-rating/history, derived
> levels). Today (27/7) is the first day matches actually move the rating.
> **Next candidates (none started):** watch the first real days of ELO in
> the wild (chips/curve/coach line render on real entries); mis-anchored-
> opponent report (deviation detector from the backtest scripts → a
> Database-tab section) once matches accumulate; re-run scale_backtest.py
> after ~2-3 months; old audit debt (delete retired video pipeline, rename
> tabs/video-analysis, SQLite FK pragma, build_week/_build_grid dedup).

> **HANDICAP_SCALE backtest → 0.5 (user picked, 2026-07-27).** Re-ran the
> grid with the PRODUCTION engine on the 23 pre-anchor handicapped matches
> (copy DB, anchor temporarily 2026-05-01): bias grows monotonically with
> scale (log-loss 0.227 at scale 0 vs 0.548 at 1.0) — results track the
> RAW gap; most plausible cause is kèo-selection (chấp is offered exactly
> when the true gap exceeds the anchors). User chose the 0.5 midpoint:
> 2-2-2 = +75, 4-4-4 = +225, 5-5-5 = +300. Ladder-shape tests pin scale
> 1.0 via monkeypatch; scratchpad harness: scale_backtest.py — re-run
> after months of post-anchor data.
>
> **LEGACY vs-LEVEL LABELS RETIRED (plan approved + built 2026-07-27).**
> Relative levels (dưới/ngang/trên cơ) now DERIVE from points vs my
> CURRENT dynamic ELO (service.level_from_points; per-match grouping uses
> the at-match-time snapshot via _level_of); a 4th bucket "unrated"
> (= "chưa có điểm") covers players without points.
>   - `tracker_player.level` column FROZEN: never written again (creates
>     get the column default, updates ignore payload.level; _level_vs_me
>     deleted); data kept, PlayerIn.level still accepted for old clients.
>   - match_to_out(m, my_points) derives opponent/opponent2/partner_level;
>     build_week reuses its ELO replay pass for my_points; router CRUD
>     passes compute_my_rating().current.
>   - build_match_stats + build_handicap_split group by derived level;
>     _LEVEL_ORDER gained "unrated". API field names/values unchanged
>     (below/equal/above/unrated) so FE shapes stayed put.
>   - Head-coach: _LEVEL_VI + level/handicap render loops gained unrated;
>     prompt explains levels are derived from points and forbids concluding
>     from the "chưa có điểm" group.
>   - FE: PlayerLevel union + LEVELS gained "unrated"; PlayerPicker chips
>     now show POINTS + real rank ("1550 · D", grey "chưa xếp" when null)
>     instead of Trên/Ngang/Dưới; MatchEditor keeps the relative word but
>     it's now derived (dynamic). NOTE: groupings shift as my rating moves
>     (e.g. I hit 1010 → a 1000-point player flips ngang→dưới cơ) — correct
>     behaviour for a relative measure, by design.
>   - GOTCHA hit during the work: a PowerShell -replace pipeline corrupted
>     router.py's UTF-8 (mojibake) — restored via git checkout + Edit tool.
>     Lesson: never round-trip UTF-8 source through Get-/Set-Content.
>   - 58/58 pytest (frozen-column test replaces the derive test; stats
>     fixtures now points-based), build + gen:api clean, smoke on real-DB
>     copy: below 6 / equal 22 / above 47 / unrated 0.

## Earlier same day (2026-07-27) — ELO Phase 2 (display + coach)

> **Phase 2 built 2026-07-27 (uncommitted, includes the re-anchor guard
> below):**
>   - **rating.py extracted** — everything ELO now lives in
>     `tracker/rating.py` (constants, anchor store, snapshots, handicap
>     ladder, replay engine); service.py re-exports the old names
>     (compute_my_rating, get/set_my_points, snapshot_match_points,
>     get_my_anchor_date, handicap_bonus) so router/tests/_level_vs_me keep
>     working. service.py 1720 → ~1500 lines.
>   - **Replay refactor:** `rating.replay(db)` returns (final, ReplayStep[])
>     — the single engine behind the current rating, per-match ±Δ and the
>     daily curve. `skip_reason(m, anchor)` is the single source of truth
>     for why a match doesn't count ("nonplaying" | "before_anchor" |
>     "no_opponent" | "no_result" | "unrated").
>   - **±Δ per match:** WeekResponse matches now carry elo_delta/elo_status
>     (annotated in build_week, one replay pass). MatchEditor shows a green
>     +Δ / red −Δ chip per counted match; ACTIONABLE skips get a muted
>     "không tính" chip with the reason tooltip (no_opponent/unrated/
>     no_result). before_anchor + nonplaying stay untagged — nothing to fix.
>   - **Daily curve:** GET /tracker/my-rating/history (anchor day + last
>     rating of each day with counted matches; replayed, nothing stored) →
>     Database tab renders a LineChart card "Đường điểm ELO" (values
>     re-based near min so the ~950 curve doesn't flatten; gridlines map
>     back to real ratings). Chart hidden until ≥2 points.
>   - **"Còn X tới E" chip** next to the big rating on the Database card
>     (E floor = 1201, rating.RANK_E_FLOOR).
>   - **Coach learns ELO:** bundle match_sum.my_elo {current, anchor,
>     anchor_date, counted_matches, to_rank_e}; context gets an "ĐIỂM ELO
>     ĐỘNG" line (blank for old snapshots); SYSTEM_PROMPT: ELO trend is the
>     #1 objective progress yardstick, ahead of raw win-rate (biased by
>     playing up / handicaps).
>   - 57/57 pytest (history curve + week annotation test), build + gen:api
>     clean; smoked on a real-DB copy (pre-anchor matches → before_anchor).
>   - NOT done yet (next candidates): retire legacy vs-level labels (plan
>     first); HANDICAP_SCALE backtest + mis-anchored-opponent report after
>     months of data; old audit debt list.

## Earlier (2026-07-26) — ELO Phase 1 complete + re-anchor guard (guard ships in the Phase 2 commit)

> **Post-review bugfix (2026-07-26, uncommitted):** saving "Điểm của tôi"
> UNCHANGED used to re-anchor at today and silently drop every replayed
> match. Now: set_my_points is a no-op when the value equals the stored
> points, and the FE Lưu button is disabled (with tooltip) until the draft
> differs. Test added in test_manual_edit_becomes_new_anchor. 56/56, build
> clean.
>
> **Code review verdict (same session):** ELO code otherwise clean — no
> refactor needed NOW; extract tracker/rating.py + split compute_my_rating
> into a per-step _replay() WHEN Phase 2 starts (it needs per-match Δ and a
> daily series anyway; doing it earlier = doing it twice). Next-step list
> (ranked): Phase 2 display (±Δ per match + "không tính" tags in
> MatchEditor, /my-rating/history + chart, "còn X tới E" chip) → coach
> bundle learns ELO (rating + trend + movers replaces raw win-rate
> "lên trình" talk) → retire legacy vs-level labels (plan first) →
> HANDICAP_SCALE backtest + mis-anchored-opponent report after 2-3 months
> of data → old audit debt (delete retired video pipeline, rename
> tabs/video-analysis, SQLite FK pragma, build_week/_build_grid dedup).

> **PHASE 1b — HANDICAP FOLDING, decided and built 2026-07-26 (uncommitted).**
> User ladder: each preset rung = +50 Elo for the RECEIVER — 0-2-0→50,
> 2-0-2→100, 2-2-2→150, 2-3-2→200, 3-2-3→250, 3-3-3→300, 3-4-3→350,
> 4-3-4→400, 4-4-4→450, 4-5-4→500, 5-4-5→550, 5-5-5→600 (max). Implemented
> as a FORMULA, not a table (service.handicap_bonus): s = handicap points
> normalized to a 3-set sum → bonus = 25×s (s ≤ 6) else 50×s − 150, capped
> at s=15 — so uniform 1-1-1 (75) and free-digit "Khác…" patterns
> (4-2-0-2-4 → 210) get consistent values. Knob HANDICAP_SCALE = 1.0.
>   - **FULL bonus, NO cap (user corrected mid-discussion):** a first
>     reading ("chấp chỉ thu hẹp khoảng cách") was briefly implemented as
>     a cap-at-the-gap; the user clarified that sentence described typical
>     kèo practice, NOT a formula rule — the receiver gets the full ladder
>     value even past the opponent's rating. Consequences are the point:
>     win as chấp-favourite → tiny gain; lose as chấp-favourite → big
>     deduction ("được chấp nhiều mà thua thì xứng đáng bị trừ nhiều").
>   - **Doubles (user rule, mid-discussion):** the chấp ELO belongs to ONE
>     member, not both — on the team-average scale bonus/2, then the cap.
>     (Counterpoint stated once: mechanically a team chấp shifts set scores
>     like in singles, arguing full value; user's sum-of-two-ELO model says
>     half. User's rule shipped.)
>   - Sign source: stored signed `handicap` (+N give / −N receive); rating
>     eligibility no longer excludes handicapped matches. MatchEditor
>     dropdown gained 4-5-4, 5-4-5, 5-5-5 presets (5-5-5 = max). Card note:
>     "trận (đơn + đôi, chấp đã quy đổi)".
>   - **Sanity analysis on the 20 pre-anchor handicapped matches** (they
>     never touch the live rating): results tracked the RAW gap as if chấp
>     didn't exist (receiving: 0/13 actual vs 0.29 expected-with-bonus;
>     giving: 71% actual vs 34%) — flagged as possible ladder overvaluation
>     OR mis-set anchors of frequent chấp partners; sample too small/
>     concentrated to override the user's ladder. Revisit HANDICAP_SCALE
>     with a backtest after months of post-anchor data. NOTE: an earlier
>     message misattributed 1200 to Tuấn gỗ — he is 1550 (D) in the DB; his
>     3× "4-4-4, thua 0-3" results are CONSISTENT with the ladder (E≈0.30).
>   - 56/56 pytest (ladder rungs/custom/cap, gap-cap integration, doubles
>     half rule), build clean. Restart start.bat.

## Earlier same day (2026-07-26) — Phase 1a snapshots (committed `74cb256`)

> **AT-MATCH-TIME SNAPSHOTS (user decision + built 2026-07-26, uncommitted).**
> User corrected the replay semantics: raising an opponent's static points
> later must NOT rewrite old matches — the new value applies only from the
> raise onward. Replay previously used CURRENT points everywhere. Built the
> federation-style fix (FFTT/USATT rate with points as of match day):
>   - `tracker_match` gains `opp_points_snap` / `opp2_points_snap` /
>     `partner_points_snap` (seed add_missing_columns; NULL on all existing
>     rows). POST /matches freezes the involved players' current points onto
>     the row; PUT re-snapshots ONLY slots whose PLAYER changed (score/date
>     edits keep the original snapshot).
>   - compute_my_rating prefers snapshots; NULL falls back to current points
>     (legacy/backfilled rows).
>   - ACCEPTED TRADE-OFF (stated to user): fixing a TYPO in a player's
>     points no longer heals already-played matches — re-pick the player in
>     those matches to refresh the snapshot, or accept the error.
>   - 53/53 pytest (snapshot freeze/re-snapshot/fallback + API wiring),
>     migration smoke-tested on a real-DB copy. Restart start.bat.
>
> **ELO history by day:** NOT stored anywhere (user asked 2026-07-26) — by
> design. Any time series is reconstructable by replaying and sampling per
> day; Phase 2 adds GET /tracker/my-rating/history for charts. With
> snapshots the reconstruction is now stable against later points bumps.

## Earlier same day (2026-07-26) — ELO Phase 1a first cut (committed `da1efcd`)

> **GO decision (user, 2026-07-26):** code with the settled constants,
> scoped to EVEN (handicap=0) SINGLES matches only. The other cases
> (handicap folding, doubles, unrated opponents) are NOT dropped — they
> are deferred, to be added later on top of this base. Also requested: a
> THIRD match kind "tournament_match" so tournament matches can be INPUT
> from now on.
>
> **Built this batch (2026-07-26, committed `da1efcd`):**
>   - **Rating service** (tracker/service.py "my dynamic rating" section):
>     `compute_my_rating` replays eligible matches from the anchor — no
>     stored deltas; edit/delete/backfill self-corrects. Eligible: singles,
>     playing, named opponent WITH points, handicap 0 + no pattern, date >=
>     anchor (inclusive), category in ELO_KIND_MULT. Constants live there:
>     ELO_K_BASE=12, kind t 0.5/1.0/1.5, margin m 1.25 sweep / 0.75 decider.
>   - **Anchor:** `tracker_setting` my_points (existing) + new key
>     `my_points_date` (default 2026-07-27). PUT /my-rating = new anchor at
>     TODAY (inclusive — today's matches still count); GET/PUT now return
>     `{points (anchor), current (replayed), anchor_date, counted_matches}`.
>   - **tournament_match category** seeded (sort 6, before racket_time).
>     Grid + MatchEditor pick it up generically (any type=="match" row).
>     Match Stats filter + router pattern + FE chip gained "tournament".
>     Racket time & directive-progress already category-agnostic — no change.
>   - **Wording fixed** (the official≠giải trap): coach bundle now reports
>     "THEO LOẠI TRẬN: đánh chơi · đánh độ nhẹ · đánh giải" (3 kinds, new
>     tournament stats call), prompt rule updated (pressure rises by kind);
>     head-coach sources panel FE shows đánh chơi/đánh độ/đánh giải.
>   - **Database tab card:** big number = CURRENT replayed rating; "Sửa"
>     edits the anchor; note line shows "neo X từ dd/mm/yyyy · đã tính N
>     trận đơn đánh đồng".
>   - **Verified:** 50/50 pytest (3 new in test_rating.py: formula/kind/
>     margin math, out-of-scope skips, anchor re-anchoring), npm build clean,
>     gen:api regenerated, smoke on a real-DB copy (seed adds the category,
>     rating = 950/0 counted — correct, anchor is tomorrow).
>   - **Restart start.bat** to seed tournament_match + load the new API.
>   - **Deferred next:** Phase 1b handicap folding (constant C, backtest
>     harness ready in this session's scratchpad); doubles/unrated policy;
>     Phase 2 display (±Δ per match, chart, "còn X tới E", coach bundle
>     rating trend); retire legacy vs-level labels (plan first).
>
> **DOUBLES — DECIDED + BUILT (2026-07-26, uncommitted).** User picked
> option B ("đánh đôi cũng rất quan trọng… nên tính vào"): doubles COUNT.
> Compare TEAM AVERAGES on the same /400 curve (user's original sum idea
> would double the sensitivity). Attribution d: proposed 0.5, but USER
> OVERRODE to **d = 1.0** ("tác động của tôi trong trận đánh đôi vẫn phải
> tốt nếu thắng — tính thắng như đánh đơn") — a doubles result moves the
> rating exactly like a singles one, BOTH ways (partner's bad day costs
> full points; consequence was stated and accepted). ΔR = 12 × t × d × m ×
> (S − E) with d kept as a knob (ELO_DOUBLES_MULT = 1.0). Eligibility:
> partner + BOTH opponents named and rated, else skipped; handicapped
> doubles wait for Phase 1b. Card note: "trận đánh đồng (đơn + đôi)".
> Even-teams official 3-0 example: +7.5, same as singles. 51/51 pytest,
> build + gen:api clean. Alternatives A (singles-only rating, FFTT/USATT
> style) and C (separate doubles rating) were rejected by the user.

> **Where we are:** user redirected Phase 1: build the update rule for EVEN
> (handicap = 0) SINGLES matches FIRST; handicapped matches get their own
> analysis later (Phase 1b). New hard requirement: SET MARGIN must matter —
> a 3-0 win gains more than a 3-2 win; an 0-3 loss drops more than 2-3.
>
> **Reference systems studied (user request) before planning:**
> - FFTT (France): lookup table by rating gap, ASYMMETRIC normal vs upset
>   (gap 200: normal win +2 / normal loss −1, upset win +17 / upset loss
>   −12.5; gap 500+: normal 0/0, upset +40/−29). Tournament coefficients
>   0.5–1.25. Monthly batches.
> - USATT (US): SYMMETRIC exchange table by point spread — expected result
>   8→0 points as the gap grows 0→238+, upset 8→50. Table-based Elo.
> - BBTV (VN): rank bands identical to our shared/rank.ts scale (H ≤800 …
>   A* >2200), new players seeded at band midpoint, tournament placement
>   bonuses (+50/+30/+20/+10 singles); the actual per-match exchange table
>   is behind a Google Drive link — NOT retrievable, don't cite it as known.
> - Invariants across all three: winner NEVER loses points, loser NEVER
>   gains; upsets move far more than expected results; NONE uses set score —
>   margin sensitivity is OUR extension, not borrowed.
>
> **Revised formula proposal (SUPERSEDES the earlier "S = set share" idea —
> set-share would SUBTRACT points on a sloppy 3-2 win over a weak opponent
> and could ADD points on a close loss, both contradicting the user's spec
> and all 3 references):**
>     ΔR = K × m × (S − E),  S = 1 win / 0 loss,
>     E = 1/(1+10^((R_opp − R_me)/400)),
>     m (margin multiplier) = 1.25 sweep (3-0, 2-0, 4-0) /
>                             1.0 normal / 0.75 deciding set (3-2, 2-1, 4-3).
>   Open decision #1 from the previous session is thereby resolved as
>   "binary S + margin multiplier", NOT set-share. K proposed 20 — but the
>   backtest, not debate, picks the final constants.
>
> **Per-match-kind K — t APPROVED by user 2026-07-26 ("0.5, 1 và 1.5 ok").**
> User redefined the kinds:
> practice = đánh chơi (casual), official = đánh độ nhẹ (small stakes,
> nước/10-20k), tournament = real tournament play. Proposal: one more
> multiplier t on the same formula — ΔR = K_base × t × m × (S − E):
>     practice t = 0.5 (K_eff 10) · official t = 1.0 (K_eff 20) ·
>     tournament t = 1.5 (K_eff 30, PLACEHOLDER — no tournament matches are
>     logged yet, so the backtest cannot tune it; revisit when data exists).
>   Precedent: FFTT event coefficients 0.5–1.25. Backtest grid should also
>   sweep the practice coefficient {0.4, 0.5, 0.75, 1.0}.
>
> **Deferred feature (user: "sẽ làm sau"): tournament_match category.**
> Today matches live in 2 seeded categories (practice_match/official_match,
> seed.py); adding tournament_match touches: seed, match-stats category
> filter (_CATEGORY_KEY service.py:1066 + router pattern + FE chips/types),
> directive-progress match counts, racket time, coach bundle. WORDING TRAP:
> the coach bundle/GUI currently call official "TRẬN GIẢI/trận giải"
> (head-coach index.tsx:270) — under the new semantics official = đánh độ,
> tournament = đánh giải; relabel when the kind lands.
>
> **ANCHOR DECISION (user, 2026-07-26): rating starts counting on
> 2026-07-27.** All older matches in the DB are IGNORED by the rating —
> first anchor = (2026-07-27, 950). Replay-from-anchor handles this natively.
>
> **BACKTEST RAN 2026-07-26 (scratchpad only, DB copy — no app code yet).**
> Purpose shifted to sanity check + volatility sizing since old matches
> won't count. Results:
>   - Only 33 eligible even rated singles matches exist (2026-05-29..07-23;
>     17 practice / 16 official; 11W-22L = 33%). 133 singles rows have NO
>     named opponent (mostly Mar–May imports — moot now, but going forward a
>     match only moves the rating if the opponent is named AND rated);
>     20 matches handicapped (Phase 1b).
>   - Sanity: replayed final rating lands 906–941 vs seed 950 across the
>     whole grid (K 12–32 × t_practice 0.2–1.0 × m on/off) — user's 33% win
>     rate vs median-1050 opponents ≈ expectation at ~950, so the 950 seed
>     and the static anchors are mutually consistent. No opponent flagged as
>     mis-entered (Trần Quang Vinh 1200: 3W-5L ≈ slightly above the ~0.2
>     expectation, not anomalous).
>   - m on/off changes the final by only ~5 pts; t_practice 0.2→1.0 by
>     ~15 pts. Constants are NOT identifiable from 33 matches — they must be
>     sized for the FUTURE volume instead.
>   - Volatility sizing: user corrected the volume target to ~20 matches/
>     week (not 30–40) and set the signal timescale: skill moves over 3–4
>     MONTHS, never weeks ("3 tháng 4 tháng lên là nhanh"), and may DROP
>     first (he loses a lot — a slide below 950 is the system working, not a
>     bug; backtest suggests the slide is shallow, replay lands ~930).
>     Noise math at 20/week: K_base 12 → ~±20/week luck swing, 16 → ~±25,
>     20 → ~±32. With a 3-4-month signal horizon, minimize noise: K=12
>     still tracks +40–90 pts/quarter at 5–10% sustained overperformance.
>
> **CONSTANTS SETTLED 2026-07-26 (t/m/anchor approved by user; K_base=12
> agreed after two rounds of volume/timescale discussion):**
>     ΔR = 12 × t × m × (S − E)
>     t = 0.5 practice / 1.0 official / 1.5 tournament (tournament is a
>         placeholder until tournament matches are actually stored)
>     m = 1.25 sweep / 1.0 normal / 0.75 deciding set
>     Anchor: (2026-07-27, 950); older matches never counted.
>     Eligible: singles + named rated opponent + handicap 0 only.
>     Even-opponent 3-0 examples: practice +3.75 / official +7.5 /
>     tournament +11.25.
>
> **Plan (proposed 2026-07-26, NOT yet approved — code only after OK):**
>   1. BACKTEST script (read-only, runs on a DB copy): replay all even rated
>      singles matches in date order over a grid of variants (K ∈ {16,20,24,
>      32} × m on/off); outputs rating curve over time, final rating,
>      biggest single-match movers, and opponents whose results deviate most
>      from expectation (mis-entered static points suspects). User picks the
>      constants from real numbers.
>   2. Rating service (after constants OK'd): replay from anchor (agreed
>      earlier — no stored deltas; PUT my-points = new anchor), counting
>      ONLY singles + rated opponent + handicap 0; doubles/unrated/
>      handicapped matches skipped for now.
>   3. Minimal display only: computed rating on the Database my-rating card
>      (full Phase 2 display work stays deferred).
>   4. Phase 1b: handicap folding (the C constant) analysed with the same
>      backtest harness.

## Earlier (2026-07-25) — ELO Phase 1 first proposal (superseded above)

> **Where we are:** all 70 players have points (H:6 G:28 F:14 E:9 D:7 C+:6);
> the user's own rating is the default 950/G. The ELO roadmap was presented
> as 3 phases; user said: start with PHASE 1 ONLY (the formula), do NOT
> discuss phase 2/3 yet. User left mid-discussion — NEXT SESSION: continue
> the Phase 1 debate below until the 3 open decisions are settled, get an
> explicit OK, only then code.
>
> **PHASE 1 (proposed, NOT yet agreed) — update formula for the user's
> dynamic rating vs static anchors:**
>   - Scope: SINGLES playing matches vs RATED opponents only. Doubles and
>     unrated opponents don't move the rating (UI must say so per match).
>   - Standard Elo with handicap folded into the opponent's effective
>     rating: `R_eff = R_opp + C × handicap` (signed int from the DB; the
>     per-set average already covers patterns like 2-0-2).
>     `E = 1/(1+10^((R_eff − R_me)/400))`, `R_me += K × (S − E)`.
>   - Architecture (key decision, recommended): NO stored per-match deltas —
>     REPLAY. Store an anchor (date, points=950); current rating = replay all
>     singles matches since the anchor. Editing/deleting/backfilling old
>     matches self-corrects. A manual edit of "Điểm của tôi" in the Database
>     tab = a new anchor from that day.
>   - OPEN DECISIONS (user has NOT answered yet):
>     1. S = set share (3-2 → 0.6; recommended — smoother, rewards close
>        losses vs strong opponents) vs plain win/loss 1/0.
>     2. K factor: proposed 20 per match.
>     3. C (Elo per handicap point/set): proposed ~50, but the REAL value
>        comes from a backtest — replay the user's full singles history and
>        tune constants so the replayed rating converges near ~950. The
>        backtest also flags players whose static points look mis-entered
>        (frequent opponents with results far off expectation).
>   - Phases 2 (display: auto card, ±Δ per match, chart, "còn X tới E",
>     coach bundle) and 3 (retire legacy labels from analytics/picker) were
>     shown but the user explicitly deferred discussing them.
>
> **Also pending (needs a plan first):** retire vs-below/equal/above from
> Match Stats analytics + picker option chips in favour of points comparison.
>
> **Wording (user decision):** never say "điểm BBTV" in the GUI — just
> "điểm". Legacy labels (trên/ngang/dưới cơ) are hidden from the Database
> tab; the DB column stays and is still used by Match Stats/coach bundle.
>
> **Fixed this batch — points vanished on reload (report: "refresh mất hết
> điểm"):** `player_to_out` built PlayerOut by hand and OMITTED `points`, so
> every player API returned points=null; the tab only looked right while
> local state patched saves. Data was never lost. Fix: pass `points=p.points`.
> Test gap closed: tests asserted ordering + ORM values but never the
> serialized response — now assert points in `list_players_db` output, before
> and after update.
>
> **Built this batch — points-first add-player flow:**
>   - PlayerPicker "+ Thêm" asks for POINTS (optional, empty = unrated) with
>     a live rank chip instead of the below/equal/above buttons; gai checkbox
>     kept. New players land in the Database tab automatically (same table).
>   - Backend derives the legacy label from points vs the user's rating
>     (same rank band = equal — service._rank_band/_level_vs_me, mirrors
>     shared/rank.ts) so old vs-level analytics stay coherent. PlayerIn.level
>     is now OPTIONAL (None): creates derive it, updates leave it untouched.
>   - Database tab: legacy-label column removed; save feedback added (green ✓
>     fades ~1.5s on success, red ✕ + red border on failure, ● = unsaved).
>   - Sorting was already points-desc; it only LOOKED alphabetical because of
>     the serialization bug above.
>   - 47/47 pytest, build clean.
>
> **Earlier same day — new "Database" tab (🗄️, after Training Center):**
>
> **ELO design pivot (user decision):** only the USER's rating is dynamic;
> every other player has STATIC points maintained BY HAND (user bumps them
> manually if someone improves). BBTV Open scale: G 800–1000, F ≤1200,
> E ≤1400, D ≤1600, C ≤1800, B ≤2000, A ≤2200; <800 = H (rank derives from
> points — frontend/src/shared/rank.ts). User seeds at 950 (G), stored in
> `tracker_setting` key `my_points`, NOT as a player row.
>   - Backend: `tracker_player.points` INTEGER NULL (seed migration) +
>     `tracker_setting` key-value table (create_all) holding `my_points`
>     (default 950). PlayerIn.points=None means "leave unchanged" so the
>     picker's pips toggle can't wipe ratings. GET /tracker/players-db (all
>     70 players + matches_played counted across opponent/opponent2/partner,
>     rated first by points desc, unrated last alphabetically),
>     GET/PUT /tracker/my-rating.
>   - FE `tabs/database/` (api/types/index) + styles/database.css +
>     registry entry: my-rating card (edit inline; noted as the only dynamic
>     rating), search box, "Đã xếp điểm x/70" progress, table rows: points
>     input (save on blur/Enter, ● = unsaved), auto rank chip, gai checkbox
>     (instant save), match count, legacy label muted. Local patch after
>     save — no reload, keeps scroll position while entering 70 rows.

## Earlier (2026-07-25, night) — handicap memory per opponent (committed `9629149`)

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

The Coach tab needs **Ollama running** (`ollama serve`, usually a background
service after install) with `qwen3.5:9b` pulled (falls back to `qwen3:14b` —
see `backend/app/core/settings.py`). All AI runs locally — no network.
