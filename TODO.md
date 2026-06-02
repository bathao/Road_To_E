# TODO — Table Tennis Coach

Status: [ ] pending · [~] in progress · [x] done

## Next (check 2026-06-03)
- [ ] **Verify imported data** against the original Excel screenshots
  (1–8 Mar, then 23 Mar – 1 Jun). Fix any OCR/transcription mistakes in the app.
- [ ] Then **commit + tag v0.3** — shared timeline, Analysis comparison charts,
  auto-red Overall, the 3 `import_*.py` scripts + imported data, dead-code cleanup.

## Tab 1 — Daily Tracker — DONE
- [x] Grid, week/day cells, duration chips, dropdown match editor, export
- [x] Physical Training checklist (yellow at ≥70%)
- [x] Auto Overall (green / yellow / red)
- [x] Future-day blocking; open on latest week with data
- [x] Inline Analysis (summary cards + Columns/Line comparison chart + category bars)
- [x] Shared timeline driving grid + Analysis together
- [ ] Speedups: Quick add Today / Copy yesterday / Repeat last week (deferred)

## Future tabs (not started)
- [ ] Training Plan
- [ ] Motivation / goals
- [ ] Tactics, supplementary drills (each adds its own `<feature>_*` tables)

Note: Analysis is built inline in Tab 1, not a separate tab.
