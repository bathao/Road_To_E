# Exercise media (Training Center)

Image resolution per exercise, in priority order:
1. **Real GIF** you drop here as `<key>.gif` (highest fidelity) — wins if present.
2. **Bundled pose illustration** — a schematic SVG under `poses/`, mapped per
   exercise in `frontend/src/tabs/training-center/constants.ts` (`POSE`). These
   ship by default so every exercise has a relevant figure (no 🏋️ placeholder).
3. 🏋️ emoji — only if both above are missing.

So you don't *need* to add anything; but dropping a real `<key>.gif` here upgrades
that exercise's card automatically (rebuild the frontend / `start.bat` to pick up
new files, since the app serves the built `dist`).

Keep them small (the repo is local-only, no CDN). A short looping GIF or a single
clear demo frame is enough.

## ⚠️ Knee-safe program

The program is designed for grade-1 knee osteoarthritis: NO deep squats, lunges,
or jumping. Exercises are low-load quad/glute/hip/calf work + rotational core +
balance. Keep any demo media consistent with that (shallow angles, no impact).

## Filenames

`<key>.gif`, where `<key>` is the exercise key from
`backend/app/features/training/program.py` (the first argument of each
`Exercise("key", …)` — e.g. `quad_set.gif`, `plank.gif`, `wall_pushup.gif`).
That file is the single source of truth; a hand-maintained list here kept
drifting out of date, so it was dropped (2026-07-29).
