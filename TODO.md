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
  PROGRESS.md 2026-07-27 notes if lost.
- [ ] **Tournament ELO multiplier** (`t = 1.5`) is still a placeholder — the
  first real tournament matches exist now (Homyland2, 2026-08-01, 4 matches)
  but one event is far too little; revisit after several tournaments.

## Open — feature ideas (no blocker, just not built)

- ~~Entry speedups (Quick add Today / Copy yesterday / Repeat last week)~~ —
  DROPPED by the user 2026-07-29 ("ko làm"); don't re-suggest.
- [ ] **Motivation tab** (🔥) — the only registry entry still disabled.
  ON HOLD: the user will say when to design it — don't propose proactively.
- [ ] **Filtered ELO deltas** (per discipline/category) in the breakdown —
  explicitly cut from v1 (a filtered rating_end would lie; filtered deltas
  are still an honest option). Only if a real question needs it.

## Watch list (not actionable yet)

- [ ] Homyland2 (2026-08-01) now shows in the Profile Tournament Record
  (smoke-verified: Doubles · Stopped at 1/8 · 2W-2L, 4 matches + ELO) →
  user to eyeball the card/detail in the GUI once.

- [ ] First real Recap run (Coach tab → Recaps → Generate; rolling last
  7/30 days ending at the button press) → check the Vietnamese output
  quality and that the stats row + prev-window diffs read sane.

- [ ] First tournament entered via the Daily Tracker → check the coach
  bundle's "đánh giải" split and the t=1.5 delta look sane.
- [ ] First real Coach & Recap entries (advice + ticking done) → check the
  coach bundle's "HLV TRỰC TIẾP ĐANG DẶN" section reads sane and the AI
  actually schedules the open advice into week plans.
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
