# TODO — Road To E

Status: [ ] pending · [~] in progress · [x] done. Live narrative log lives in
`PROGRESS.md` (newest first); this file only tracks OPEN work so it stays
scannable. Last full sync: 2026-07-29.

## Open — needs data to accumulate first

- [ ] **Mis-anchored-opponent report**: surface frequent opponents whose
  results deviate hardest from expectation (their static points are probably
  wrong). Deviation detector already prototyped in the backtest scripts;
  needs a few more weeks of post-anchor matches before the numbers mean
  anything. Candidate home: a Database-tab section.
- [ ] **"Road To E" ETA projection**: from the ELO trend, project when the
  rating crosses 1201 (rank E floor). Same blocker — needs weeks of trend.
- [ ] **Re-run `scale_backtest.py`** (~Oct 2026) to re-check
  `HANDICAP_SCALE = 0.5` against real post-anchor handicapped matches
  (chosen 2026-07-27 from a backtest of 23 pre-anchor matches; kèo-selection
  suspected). Harness lives in the session scratchpad — recreate from
  PROGRESS.md 2026-07-27 notes if lost. Same pass: re-check
  `ELO_DOUBLES_HANDICAP_MULT = 1.5` (chosen 2026-08-31 from 19 doubles-chấp
  matches, log-loss bottom at 1.5) once more doubles-chấp matches exist.
- [ ] **Tournament ELO multiplier** (`t = 1.5`) is still a placeholder — the
  first real tournament matches exist now (Homyland2, 2026-08-01, 4 matches)
  but one event is far too little; revisit after several tournaments.

## Open — feature ideas (no blocker, just not built)

- [ ] **Per-EVENT points tier for tournaments** (spotted 2026-08-20,
  UNBLOCKED 2026-08-24 — BBTV is over): BBTV Open Lần 3 lived as 5
  duplicate cards (tiers 1100/1200/1300/1500/Open) because `points_limit`
  sits on the tournament while each EVENT (nội dung) has its own tier.
  The weekend proved the pain (5 cards × ☠ churn). Candidate: tier on
  tournament_entry (like `division`), then merge the 5 cards — migration
  must keep the existing per-tier match links intact. Waiting for the
  user's go.

- ~~Entry speedups (Quick add Today / Copy yesterday / Repeat last week)~~ —
  DROPPED by the user 2026-07-29 ("ko làm"); don't re-suggest.
- [ ] **Motivation tab** (🔥) — the only registry entry still disabled.
  ON HOLD: the user will say when to design it — don't propose proactively.
- [ ] **Filtered ELO deltas** (per discipline/category) in the breakdown —
  explicitly cut from v1 (a filtered rating_end would lie; filtered deltas
  are still an honest option). Only if a real question needs it.

## Watch list (not actionable yet)

- [ ] **Shared read-only copy on Render — LIVE 2026-09-25 at
  https://road-to-e.onrender.com** (`0eafc2c`, Docker build passed in 1 min,
  no access code by the user's choice). Watch: (a) the coach's first open
  — the first REAL "pushed" run of the ☁ Sync to coach button is DONE
  (`39bf375` "DB sync 2026-09-26" 19:28, DB + stamp only, pushed; probed
  from outside at 19:31: Render already served `last_sync 19:28`,
  last-date 26/09, 180 counted matches — redeploy ≈ 2 min). User then
  reported "web vẫn không thấy" → the SPA tab was opened before the
  redeploy and holds old state; a page reload is required, the API and
  index.html are `no-store` so nothing else caches; (b) whether the ~50 s wake-up after 15 idle minutes bothers
  the coach — then a pinger (cron-job.org → `/api/health`, every 10 min);
  (c) DONE 2026-09-26 — the coach opened the link on a phone ("hiển thị
  rất tệ"): write affordances now hidden under `.share-mode`, the Journal
  sticky-board CSS order bug and the Tournament Record squeeze fixed (see
  PROGRESS). Grid cells still open the match editor on tap (read-only, it
  is the only detail view) — hide that too if the coach trips on it.

- [x] **Checkpoint the DB before committing it** (found 2026-08-23; SOLVED
  2026-09-25 — `sync.bat` runs `backend/scripts/sync_prepare.py`, which
  checkpoints the WAL before every DB commit; for hand-made commits the
  recipe below still applies): the
  app runs SQLite in WAL mode and .gitignore skips -wal/-shm, so a commit
  made while start.bat is running snapshots a STALE main file (a86bb60 /
  8abd9ad carried an ~18/08 DB state). Before any commit that includes
  backend/data/tabletennis.db: stop the app, or run
  `PRAGMA wal_checkpoint(TRUNCATE)` first. Candidate permanent fix: a tiny
  pre-commit checkpoint script. (Live case 2026-08-31: the WAL is ~239KB —
  the last days' matches + today's TC session sit there only. 2026-09-05:
  start.bat restarted 19:09 so the main file is fresh; only recap #11
  (19:12) sits in the WAL — checkpoint, then commit. 2026-09-07: restarted
  again 20:33, WAL holds only the 2 players added afterwards — same recipe,
  applied: checkpoint → WAL 0 bytes → committed as `8cc4db7` (the 24/08–07/09
  batch). Recipe works; the pre-commit script stays a nice-to-have.)
- [ ] **Journal RichArea (WYSIWYG, built 2026-08-21, committed b1cf439)** —
  partially confirmed in real use 2026-08-22: a live advice note carries
  `**...**` bold markers, so Ctrl+B + save round-trip works. Still watch:
  Telex/IME edge cases while typing, paste stays plain.
- [ ] **Database tab popover fix (2026-09-07, committed 8cc4db7)**: `.db-table-wrap`
  lost its `overflow-x: auto` (it clipped the points-intent popover when a
  search left 1–2 rows). Watch once: the table on a narrow window (it is
  width: 100% in a 900px tab, so it should shrink, not overflow the page).
  The user's interrupted edit (Phan Đức Việt 1200 → 1300) never saved —
  redo it and pick 📈 Level change / ✏️ Fix wrong entry.

- [x] **SGPP 15–16 Aug End date** — set (end_date = 2026-08-16 confirmed
  in the DB on 2026-08-25); the multi-day played rule got its live test.

- [ ] Homyland2 (2026-08-01) now shows in the Profile Tournament Record
  (smoke-verified: Doubles · Stopped at 1/8 · 2W-2L, 4 matches + ELO) →
  user to eyeball the card/detail in the GUI once.

- [x] First real Recap run — recaps #10 (24/08) and #11 (05/09) both done;
  #11's stats row + prev-window diffs verified against the DB line by line
  (5 matches / −10.2 / 0 new opponents vs 15 / +7.1 / 6) — all sane. Only
  nit: occasional garbled wording ("0% (1/1)").
- [~] First verdict/recap AFTER the 2026-08-04 prompt enhancements → check
  the coach actually (a) credits same-handicap progression (Tuấn gỗ: three
  0-3 losses then 2-3 at the same "được chấp 4" is the live test case),
  (b) names the ELO drains/sources with kèo strategy, without drifting into
  in-match tactics (still banned), and (c) the week plan covers the next 7
  days with verbatim date labels and puts Phú Thọ/Friendship prep on the
  right days (no invented dates). (b) CONFIRMED on the recap side 2026-09-05
  (recap #11 names Anh Trường +3.7 / Chung, Tuấn −4.5 / Danh −3.6 — all
  grounded in elo_by_opponent). (a) and (c) still need a VERDICT run (latest
  is #17, 16/08).
- [x] "New opponents" stat (2026-08-01; redefined 2026-08-02 to SINGLES-only
  — team-only meetings don't count) — GUI verified by the user; recap #11
  (05/09) references it correctly ("Không gặp đối thủ mới đánh đơn nào (0
  lần, kỳ trước là 6)" — the two new 31/08 doubles-only names were rightly
  excluded).
- [ ] Match snapshots don't follow Database point edits (by design). One
  mis-entered player fixed by hand 2026-08-02 (Tiến Lợi 800→850, scratchpad
  script). If this keeps happening, add a small "re-freeze points on this
  match" affordance instead of hand-editing.

- [x] First LIVE run of the Singles Tactics tab — DONE 2026-08-17 (plan vs
  Nguyễn Văn Trung: placement scheme, kèo-aware mental keys and data_gaps
  all sane; screenshot-verified).
- [ ] First plan generated AFTER a "My analysis" reflection (2026-08-17) →
  check the coach actually synthesizes the note and calls out any
  reflection-vs-data contradiction in 'overall'.

- [ ] First tournament entered via the Daily Tracker → check the coach
  bundle's "đánh giải" split and the t=1.5 delta look sane. (BBTV Open
  Lần 3, 2026-08-22..23, is now a full real dataset: 14 linked matches
  across 5 tiers — the next verdict is the live test.)
- [~] **Jump rope as a daily TC item** (final shape 2026-09-05, committed 8cc4db7;
  LIVE since the 07/09 20:33 restart — the open explosive day-4 session
  carries it as item 10/10 with target "100 jumps", 0 ticks so far; tick =
  done, counted in the Physical cell like any item).
  Watch: the first few sessions with it ticked/skipped, the knee feedback
  after impact days (pain → the item's Skip + session pain drives the bias),
  and whether the coach's THỂ LỰC muscle_volume line surfaces "Calves,
  ankles, footwork rhythm" sensibly. Orphan EMPTY table `tc_daily_log` from
  the abandoned same-day count-log v1 stays in the DB (never drop tables).
- [~] **Tracking board first live use** (built 2026-08-24, committed 8cc4db7;
  tables live since the 25/08 restart). The 25/08 first task ("Gởi 3 trận
  đấu cho Phi Vũ xem", a one-shot mis-flagged daily) was DELETED by the
  user before 31/08 — board is empty again, watch resets. Still to watch:
  a real daily ticked a few days, see the 🔥 streak; then check the next
  verdict/recap actually references "NHIỆM VỤ ĐANG THEO" (streak praise /
  neglect nudge) instead of ignoring it. **2026-09-05: still 0 rows, 12 days
  after go-live** — meanwhile the 04/09 coach advice ("3 yêu cầu từ HLV":
  foot-stamp serve, 1–2 fast long serves per set, mid-distance) + the 2
  self-drills sit in the Journal as prose. Those are the obvious first
  tasks; raised with the user. Recap #11 got `tasks: []`. 2026-09-07:
  still 0 rows (14 days).
- [ ] **First roster'd TEAM entries** (Giải F-G Liên Đoàn 12–13/09, Tử
  Trung + Phương Quang; Giải STBB 06/09, 4-name roster). Card/strip labels
  ARE rendered live now — and immediately exposed a roster-overflow bug,
  fixed 2026-08-31 (card chips wrap; strip truncates with hover title).
  Still to watch: the coach bundle line, and later the record grouping
  for a team entry. **Giải STBB plays 06/09 (tomorrow as of 05/09)** — the
  first TEAM event through the tab: match↔entry linking on a team day, the
  "đánh giải" split, the record card. F-G roster changed by the user to Tử
  Trung ONLY (Phương Quang removed); free-text team_members = "TMSKY".
  **2026-09-07: Giải STBB (06/09) left NO trace** — entry #17 has 0 linked
  matches, not ☠, no activity row on 06/09; latest match in the DB is still
  31/08. Skipped or just not logged? Asked the user. The team-event live
  test moves to Giải F-G Liên Đoàn (12–13/09) unless STBB gets back-filled.
- [ ] Advice done-lifecycle is UI-less since 2026-08-21 (the "Still working
  on" checklist was dropped; is_done stays in the DB but nothing ticks it) →
  every advice now counts as "open" forever in the coach bundle's "HLV TRỰC
  TIẾP ĐANG DẶN" section. If that section grows stale/noisy, switch it to
  recent-N coach lines (like lessons) and retire is_done + the /active
  endpoint for real.
- [~] First verdict/recap AFTER journal lessons exist (2026-08-20) → check
  the new "KINH NGHIỆM HỌC TRÒ TỰ RÚT RA" section reads sane and the coach
  actually cross-checks a lesson against the numbers. **RECAP side CONFIRMED
  2026-09-05:** recap #11 cites "theo dặn ngày 04/09" in focus_next and
  echoes the lesson's "chân ì ạch" in overall — journal material IS consumed.
  Verdict side still pending. (Recap #10, week
  18–24/08, ran DONE on 2026-08-24 with journal notes in the DB — user to
  eyeball whether the lesson/advice material actually shows up in the
  text.)
- [ ] `RACKET_MINUTES_PER_SET = 5` — user confirmed keeping it (2026-07-27,
  "thôi vậy cũng dc"); recalibrate only if session-length data ever says
  otherwise.

## Done (milestones — details in PROGRESS.md)

- [x] Tab 1 Daily Tracker (grid, editors, analysis, export) — v0.1..v0.4
- [x] Data import Mar–Jun 2026 (4 one-shot scripts, kept as provenance)
- [x] Tournaments (strip + section + coach integration), 2026-07-25
- [x] Player database + static points + my dynamic ELO (anchor + replay,
  handicap folding, doubles/1v2/2v1), 2026-07-25..27
- [x] Head Coach (verdict + directives + chat + notebook) + ELO trend input
- [x] Training Center (knee-safe program, autoregulation, weekly summary)
- [x] English UI sweep (GUI English; coach stays Vietnamese), 2026-07-28..29
- [x] Project-wide review + cleanup: video_analysis feature DELETED (tables
  kept), dead code/CSS purged, dedup (shared EloCurve, disciplines,
  resultOf…), one-replay coach bundle, scripts un-broken, docs rewritten,
  2026-07-29
