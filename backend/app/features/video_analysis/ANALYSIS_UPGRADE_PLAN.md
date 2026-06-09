# Video Analysis — Deep Upgrade Plan (master design)

Status: **design / not yet implemented.** This is the canonical design for turning
the Video Analysis "specialist coach" into a motion-aware, evidence-grounded,
time-comparable analyzer. It is written to be built **incrementally** (phases that
each ship working, low-risk) while converging on one coherent target architecture
— so we build it properly from the start instead of bolting features on.

Consistent with the project's Final goal (see `PROGRESS.md`): this tab is a **data
producer** for the future Head Coach. Therefore every upgrade here optimises for
two things at once — (1) a *better analysis the user reads today*, and (2) *richer,
structured, queryable data the brain reads later*.

---

## 1. Design principles

1. **Motion-first.** Table tennis is a sport of *movement* — swing path, contact
   point, timing, weight transfer, recovery. A general VLM fed evenly-spaced still
   frames is effectively blind to all of it. Everything below exists to give the
   coach the *motion*, not just snapshots.
2. **Evidence-grounded.** Every finding must point to *when* (timestamp / stroke
   index) and ideally *what* (an evidence thumbnail). A finding you can jump to and
   see is trustworthy; a floating sentence is not. This also gives the Head Coach
   verifiable, addressable data.
3. **Time-comparable.** Pose-derived numbers are stored as a flat metric series so
   "knee flexion 150°→140° over 6 weeks" is a query, not a re-analysis.
4. **Honest about uncertainty.** Confidence per finding, an automatic self-critique
   pass, and the existing human review gate. A general VLM *will* hallucinate
   technique; the pipeline is built to catch and discount that, not to pretend.
5. **Local-only, GPU-bounded.** Everything runs on the RTX 5060 Ti via Ollama +
   CPU MediaPipe. Designs must fit ~16 GB VRAM and stay offline.

---

## 2. Current pipeline (baseline) and where it loses information

`analyzer.analyze_file` today:

1. `trim_segment` (GPU, good — keep as is).
2. `_sample_frames` → **32 pose frames + 14 VLM frames, evenly spaced over the
   whole clip.**
3. `run_pose` → MediaPipe per frame → **aggregate mean/min/max** of stance width,
   knee flexion, torso lean, lateral sway, hand elevation.
4. `call_vlm` → **one** Ollama call: 14 stills + pose-as-text → structured JSON
   (strengths / weaknesses / serve / footwork / posture / recommendations).
5. Findings persisted as `proposed` traits; text model later synthesises `va_skill`
   + profile from *accepted* findings.

**Information lost / weaknesses (each is addressed below):**

| # | Loss | Consequence |
|---|------|-------------|
| L1 | Temporal order destroyed (14 isolated stills) | Coach can't see a swing, timing, or sequence — only postures |
| L2 | Even sampling spans dead time (ball pickup, rest) | Frames wasted on non-play; key contact moments missed |
| L3 | Pose is static aggregate only | No swing speed, body rotation, weight transfer, recovery time |
| L4 | One VLM pass, all aspects at once | Shallow; attention split; no chance to self-check |
| L5 | No evidence link | Findings unverifiable; can't jump to the moment; weak for the brain |
| L6 | No ball / table awareness | No placement, depth, tempo, or real tactical read |
| L7 | Each clip analysed in isolation | No progress tracking; can't compare to the player's own baseline |
| L8 | Only `training` / `match_points` typing | Prompt can't focus (serve drill vs footwork drill vs match) |
| L9 | Frame decoded/re-opened several times | Slower; harder to extend cleanly |

---

## 3. Target architecture

A staged pipeline with clear, individually-testable stages. Stages 0–9 below; the
**phasing in §6** says which ship when.

```
                          ┌─────────────────────────────────────────┐
  source video ──trim──▶  │  S1 Decode (single pass, timestamped)     │
                          └───────────────┬───────────────────────────┘
                                          ▼
        ┌──────────────────────┐   ┌──────────────────────┐
        │ S2 Activity + audio  │   │ S3 Pose track         │  (player side cropped)
        │  rally segmentation  │   │  per-frame landmarks  │
        └──────────┬───────────┘   └──────────┬───────────┘
                   └───────────┬──────────────┘
                               ▼
                   ┌──────────────────────────┐
                   │ S4 Stroke segmentation    │  wrist-speed peaks → strokes
                   │   (FH/BH/serve heuristic) │  with t, swing speed, phase frames
                   └──────────┬────────────────┘
                              ▼
              ┌───────────────────────────────┐   ┌───────────────────────────┐
              │ S5 Biomechanic metrics         │   │ S6 Frame selection         │
              │  per-stroke + aggregate + dyn. │   │  per-stroke montages + ctx │
              └───────────────┬────────────────┘   └─────────────┬──────────────┘
                              └──────────────┬────────────────────┘
                                             ▼
                          ┌──────────────────────────────────┐
                          │ S7 VLM analysis (multi-pass)       │
                          │  detect ▸ per-aspect ▸ self-critic │  evidence + confidence
                          └──────────────┬─────────────────────┘
                                         ▼
                  ┌────────────────────────────────────────────┐
                  │ S8 Persist: traits(+evidence), metrics,      │
                  │     strokes, evidence thumbnails             │
                  └──────────────┬───────────────────────────────┘
                                 ▼
                  ┌────────────────────────────────────────────┐
                  │ S9 Synthesis: skills, profile, progress      │
                  │     vs the player's own baseline             │
                  └────────────────────────────────────────────┘
   (S10 future: ball/table detection feeds S5/S7; video-native VLM replaces S6/S7)
```

### S1 — Single timestamped decode
One `cv2` pass that yields `(t_sec, frame_rgb)` for the sampled set and is reused by
S2/S3/S6, instead of `_sample_frames` re-opening the capture. Carries true
timestamps (frame_idx / fps) so every downstream stage can speak in seconds.
*Fixes L9; prerequisite for evidence timestamps (L5).*

### S2 — Activity + rally segmentation
- **Motion energy**: per-frame frame-difference magnitude (cheap, CPU). Low energy
  = dead time (standing, picking up balls).
- **Audio impacts**: `ffmpeg` extracts mono PCM; detect sharp onset peaks (the
  "tock" of ball-on-rubber / ball-on-table). Gives stroke *count* and *tempo*
  independent of vision, and anchors where play happens.
- Output: a list of **active segments** `[(t0,t1)]`. Sampling and pose run on these,
  not on the whole clip. *Fixes L2; partial L6 (tempo).* 

### S3 — Pose track (time series, not just aggregate)
Run MediaPipe over active-segment frames on the player's cropped side (reuse
`crop_side`). Keep the **per-frame landmark series** (wrist/shoulder/hip/knee/ankle
positions + visibility) keyed by timestamp — the raw material for S4/S5. Aggregate
stats remain but are now *derived from* the series.

### S4 — Stroke segmentation & **phasing** (add-on NC3)
From the wrist position/velocity series: detect **swing events** as peaks in playing-
hand speed. For each stroke, divide it into the **canonical phases** a coach speaks
in: `ready → backswing → forward_swing → contact → follow_through → recovery`.
The boundaries are anchored on the **contact instant** — taken from the audio impact
(S2) when available, else from a ball-contact point (S10/NC1), else approximated by
peak wrist speed. Heuristic **classification** of each stroke: forehand vs backhand
from wrist-x relative to body centre + elbow geometry; serve from clip focus + an
early near-table toss pattern. Output: ordered `strokes[]`, each
`{idx, t_contact, hand, phases:{name:[t0,t1]}, phase_frames}`.

This formalises a stroke into a **structured, comparable object** — the backbone for
everything downstream: per-phase metrics (S5), one-montage-per-stroke = its phases
(S6), the VLM reasoning *per phase* (S7), and evidence anchored to a phase (S8).
*Core of fixing L1; absorbs proposed add-on NC3 (Phasing Analysis).*

### S5 — Biomechanic metrics (per-stroke + aggregate + dynamic)
Extend beyond today's five static numbers:
- **Dynamic**: peak wrist speed (swing speed proxy), shoulder–hip separation angle
  (torso rotation / "coiling"), weight transfer (hip-x shift across a stroke),
  recovery time (stroke-end → ready position), balance (COM over base of support).
- **Per-stroke + per-phase** values + clip aggregate; all emitted as a flat
  `{name, value, unit}` list for storage (see S8 / `va_metric`). *Fixes L3; enables L7.*
- **Split-step synchronisation (add-on NC2) — advanced, gated.** When focus is
  `rally`/`match` *and* a contact anchor for the **opponent** exists (ball or audio),
  measure Δt between the player's split-step landing (vertical CoM/ankle dip→rise
  from pose) and the opponent's contact. Elite players land the split-step ≈ on the
  opponent's contact; the metric is `split_step_sync_ms` (signed) + a confidence.
  **Honest caveats baked in:** it compounds three uncertain measurements
  (own split-step + opponent contact + sub-frame alignment), needs **≥60 fps** to be
  meaningful (30 fps = 33 ms/frame is marginal), and requires tracking the
  **opponent** — which today's player-side crop deliberately discards. So it is
  optional, confidence-flagged, and only computed when its prerequisites hold.

### S6 — Frame selection for the VLM (montages)
Replace even sampling with **stroke montages**: for each of the top-N strokes, build
a small horizontal strip (backswing → contact → follow-through, 3–5 frames) as a
*single* image. The VLM reads a swing in one image. Add a few whole-frame context
shots (stance, table position). The player crop can be sent at higher resolution
(bigger subject = more visible detail) within the token budget. *Fixes L1, L2.*

**Annotated overlays (add-on NC4) — split goal, validate the VLM half.**
Draw *geometry only* on frames — pose skeleton, key joint-angle arcs, ball
trajectory, the contact frame highlighted, phase labels. Two distinct uses with
very different certainty:
- **(a) User-facing evidence thumbnails — a sure win.** The overlaid crop shown next
  to a finding ("khuỷu tay tụt ở 0:12" + the skeleton/angle drawn) builds trust
  regardless of any VLM effect. Always do this (feeds S8).
- **(b) Overlay as VLM *input* — an A/B experiment, not an assumption.** Do **not**
  draw numbers and expect an 8B model to OCR + bind them correctly — numbers stay in
  the text prompt. Overlays can also *occlude* the very thing under analysis (a
  skeleton hides the bat angle/grip) or make the model describe the annotation
  instead of the technique. So: send geometry not text, **keep the raw frame too**,
  and only keep overlay-as-input if it measurably improves findings.

### S7 — VLM analysis (multi-pass, evidence-required)
- **Pass A — detect** (exists): identity gate, unchanged.
- **Pass B — analysis**: per-aspect calls (e.g. serve / forehand+backhand /
  footwork+posture / tactics), each fed the relevant montages + the numeric pose
  facts for that aspect, and **required to attach, per finding, a `t_ref`
  (timestamp or stroke index) and a `confidence` 0..1**, or state "không quan sát
  rõ". Starts as a single enriched pass (montages + facts) and is split per-aspect
  where depth pays off. *Fixes L4, L5.*
- **Pass C — self-critique**: feed the draft findings + the same montages back and
  ask the model to flag any claim not supported by the frames/metrics; unsupported
  ones are dropped or downgraded in confidence before they become `proposed`
  traits. *Fixes L4 (hallucination).*

The numeric metrics (S5) are **ground truth the VLM must defer to** — the prompt
states pose numbers override visual guesses for things like stance width / knee
bend, so the model narrates and contextualises rather than inventing.

### S8 — Persistence (evidence-grounded + time series)
- `va_trait` gains `t_ref` + `evidence_json` (stroke idx / timestamp / thumbnail
  path) + uses existing `confidence`. UI can render a "jump to 0:12" + thumbnail.
- New `va_metric` flat table: one row per `(clip_id, name)` numeric value → trivial
  time-series queries for progress + the brain.
- Strokes/segments stored as JSON on the analysis row (`metrics_json` /
  `strokes_json`) — queryable detail without a heavy schema.
- Evidence thumbnails (montages / contact frames) saved under `VIDEOS_DIR` and
  referenced by path, like previews today.

### S9 — Synthesis + progress
Existing `synthesize_skills` / `synthesize_profile` stay. Add **baseline
comparison**: for each metric, compare this clip to the player's recent history
(from `va_metric`) and surface deltas ("forehand swing speed +8% vs last month";
"recovery time still slow"). These deltas feed both the analysis view and the
`/report` the brain consumes. *Fixes L7.*

### S10 — Ball + table tracking (add-on NC1, promoted to committed core)
Elevated from "future/exploratory" to a **committed core capability** — but
**best-effort, never a hard gate** (it degrades gracefully like pose). Three parts:
- **Table homography**: detect the 4 table corners → a plane homography. This is the
  unlock for *placement* — it maps an image-plane ball point to **table coordinates**
  (zones / depth). Without it we only have a 2D image-plane trajectory.
- **Ball detection/tracking**: a 40 mm ball at speed on a 30 fps phone camera blurs to
  a streak — classical colour/Hough is brittle (white walls/floor/clothing). The real
  tool is a **TrackNet-style CNN** (proven for table tennis) run via **onnxruntime-GPU**
  (lighter than full torch); a classical detector is the fallback. Every point carries
  a confidence; low-confidence clips simply skip ball-derived metrics.
- **What it unlocks**: shot **placement zones**, depth, rally length/tempo, and a
  precise **contact instant** that sharpens stroke phasing (S4) and enables split-step
  sync (S5/NC2). Single uncalibrated camera ⇒ placement/zone is feasible; **absolute
  speed/spin is not — we will not claim those.** *Fixes L6; anchors NC2/NC3.*

### S11 — (Experiment) video-native VLM
If an Ollama-served model can ingest short clips within VRAM, it can replace montages
(S6) and see motion directly — evaluated as an experiment, not a dependency.

---

## 3b. Reviewed add-on upgrades (NC1–NC4): verdicts & dependency order

Four proposed upgrades were reviewed critically and folded into the stages above.
Summary of the critique and where each lands:

| # | Upgrade | Verdict | Lands in | Key pushback / caveat |
|---|---------|---------|----------|------------------------|
| **NC1** | Ball tracking ("mandatory") | **Promote to committed core, but best-effort — *not* a blocking gate** | S10 | 30 fps + motion blur breaks classical detection → needs a TrackNet-style ONNX model + GPU dep; placement needs table homography; 2D-only without calibration; must degrade gracefully when the ball isn't trackable |
| **NC2** | Split-step synchronisation | **Advanced, gated, optional** | S5 | Most fragile — compounds 3 uncertain measurements; needs the **opponent's** contact (today's crop discards the opponent) + **≥60 fps**; only for rally/match; always confidence-flagged |
| **NC3** | Phasing analysis | **Strongest — promote to the backbone** | S4 | Precise phase boundaries need a contact anchor (audio/ball); pose-only contact is approximate |
| **NC4** | Drawing overlays for the VLM | **Split: user thumbnails = sure win; VLM-input = A/B experiment** | S6/S8 | Don't expect an 8B model to OCR drawn numbers (keep numbers in text); overlays can occlude/distract; validate before trusting; keep the raw frame |

**The cross-cutting dependency** is a reliable **contact-timing anchor**. Two sources:
**audio impact** (cheap, already in S2) and the **ball contact** (NC1, precise + gives
placement). Both NC2 and NC3 consume it. Hence the build order:

```
audio anchor (S2)  ──▶  phasing / NC3 (S4)  ──▶  ball+table / NC1 (S10)  ──▶  split-step / NC2 (S5)
                                   └──────────── overlays / NC4 layer on once skeleton + phases + trajectory exist
```

So phasing ships early on the cheap audio anchor and *sharpens* later when ball
tracking lands; split-step is last because it needs both the ball/opponent contact
and high frame-rate footage.

---

## 4. Data model changes (all additive, idempotent)

Follows the existing pattern: new tables via `create_all`; new columns via
`seed._add_missing_columns` (SQLite `ADD COLUMN`). No destructive migration; existing
rows preserved.

**New columns**
- `va_clip.focus` `VARCHAR DEFAULT ''` — drill focus: `serve_practice` |
  `footwork_drill` | `rally` | `match` | `free`. Drives targeted prompts (L8).
- `va_trait.t_ref` `FLOAT` — evidence timestamp (seconds), nullable.
- `va_trait.evidence_json` `TEXT` — `{stroke_idx, t, thumb_path}` JSON, nullable.
- `va_analysis.metrics_json` `TEXT DEFAULT '{}'` — per-stroke + per-phase + dynamic
  metrics (incl. `split_step_sync_ms` + its confidence when computed, NC2).
- `va_analysis.strokes_json` `TEXT DEFAULT '{}'` — stroke list with phases + segments.
- `va_analysis.ball_json` `TEXT DEFAULT '{}'` — ball trajectory points (+confidence),
  table homography, placement zones, opponent contact times (NC1; `{}` when no ball).

**New table** `va_metric` (the time-series spine for progress + the brain)
```
id           PK
clip_id      FK va_clip (CASCADE), index
name         VARCHAR index   -- e.g. 'knee_flexion_mean', 'fh_swing_speed',
                             --       'backswing_len_mean', 'split_step_sync_ms'
value        FLOAT
unit         VARCHAR
created_at   DATETIME        -- copy of clip time for ordering
```

Add the new column dicts to `_VA_CLIP_COLUMNS` / new `_VA_TRAIT_COLUMNS` /
`_VA_ANALYSIS_COLUMNS` in `seed.py`; register `VAMetric` so `create_all` builds it.
Per-phase metrics, the ball trajectory and `split_step_sync_ms` are all just rows /
JSON here — **no schema change** is needed when NC1/NC2/NC3 land, only new metric
names, so the data contract for the Head Coach stays stable across phases.

---

## 5. API / frontend touch-points (kept thin)

- `ClipCreateIn` + create form gain **`focus`** (a dropdown next to clip type).
- `AnalysisOut` exposes `metrics`, `strokes`, and per-trait `t_ref` / `evidence`.
- `TraitOut` gains `t_ref` + `evidence` so `AnalysisDetail` can render a clickable
  timestamp + evidence thumbnail (and, later, seek a `<video>` element).
- `GET /report` (the brain view) gains per-skill **trend** (metric deltas) — purely
  additive, no breaking change to existing consumers (Profile tab).
- New: `GET /clips/{id}/evidence/{thumb}` to serve evidence thumbnails (mirrors the
  existing preview/frame endpoints).

---

## 6. Rollout phases (each ships working & verified)

**Phase 0 — Pipeline scaffolding (low risk, no output change).**
Refactor to the staged structure: single timestamped decode (S1), stage functions
with config knobs, metrics emitted as a flat list internally. Output to the user is
unchanged; this is the spine everything else hangs on. Verify: same clip yields
equivalent analysis to today.

**Phase 1 — See the motion + stroke phasing (biggest quality jump).**
S2 activity/rally + **audio impacts (the cheap contact anchor)**, S4 stroke
segmentation **& phasing (NC3)**, S6 stroke montages; switch the VLM input from even
stills → montages + context. Verify on a real training clip: findings reference
actual strokes/phases; dead time excluded.

**Phase 2 — Depth, trust & overlays.** *(partly done)*
S5 dynamic + per-phase metrics; S7 evidence+timestamp+confidence per finding +
self-critique pass; clip `focus` tag → targeted prompts; **NC4(a) user-facing
annotated evidence thumbnails** + UI jump-to-timestamp. Verify: every proposed
finding has a `t_ref`; self-critique demonstrably drops an unsupported claim.
- ✅ evidence `t_ref` + confidence + UI jump-to-timestamp (commit `3e35bda`).
- ✅ clip `focus` tag → targeted prompts (`_FOCUS_VI`/`call_vlm(focus=…)`).
- ✅ self-critique pass (`self_critique`/`_apply_self_critique`, `SELF_CRITIQUE`).
- ⏳ remaining: NC4(a) annotated (skeleton/angle) evidence thumbnails; richer
  per-phase metrics beyond the current stroke dynamics.

**Phase 3 — Progress over time.**
`va_metric` persistence + baseline comparison (S9); surface deltas in analysis and
`/report`. Verify: analysing a second clip shows deltas vs the first.

**Phase 4 — Ball + table tracking (NC1, committed core, best-effort).**
S10 table homography + TrackNet-style ball tracking (onnxruntime-GPU) + placement
zones/tempo; ball-derived contact instant sharpens phasing. Verify: placement zones
plausible on a rally clip; graceful skip when the ball isn't trackable; accuracy
documented honestly.

**Phase 5 — Split-step sync (NC2) + experiments.**
S5 split-step synchronisation (needs Phase 4's contact anchor + opponent tracking +
≥60 fps footage, confidence-flagged); NC4(b) overlay-as-VLM-input A/B; S11
video-native VLM trial. Verify: metric only emitted when prerequisites hold; A/B
shows whether overlays help before they are kept.

Phases 1–3 are the committed core. Phase 4 (ball/table) is committed but best-effort
and carries a new GPU dependency. Phase 5 is advanced/experimental and gated on
Phase 4 + suitable footage.

---

## 7. Risks & honest limits (carried into the UI, not hidden)

- A general VLM **will** over-claim technique. Mitigation stack: numeric metrics as
  ground truth, evidence requirement, self-critique pass, confidence, and the
  existing human review gate. We surface confidence; we don't pretend certainty.
- **Stroke classification is heuristic** (FH/BH/serve) — good enough to focus
  attention, not a labelled dataset. Mislabels are possible and the prompt is told
  so.
- **Single uncalibrated camera**: placement zones (via table homography) are
  feasible; absolute ball speed/spin are not — we will not report them.
- **Ball tracking (NC1) is a new heavy dependency** (TrackNet ONNX + onnxruntime-GPU)
  and is unreliable at 30 fps / heavy motion blur / white backgrounds. It is
  best-effort, confidence-gated, and never blocks analysis when it fails.
- **Frame rate caps timing precision.** Phasing (NC3) and especially split-step
  (NC2) need high fps; at 30 fps (33 ms/frame) split-step sync is marginal — we flag
  low-fps clips and degrade or suppress the metric rather than report false numbers.
- **Split-step (NC2) requires the opponent**, which the player-side crop currently
  discards; enabling it means also tracking the opponent (ball or pose) — extra cost,
  rally/match only.
- **Overlays (NC4) can hurt as well as help** a small VLM (occlusion, distraction);
  the user-facing thumbnail is the guaranteed value, the VLM-input use is A/B-gated.
- **MediaPipe is single-prominent-person** and degrades in cluttered / doubles /
  far-camera footage; the side-crop + identity gate mitigate but don't eliminate.
- **More VLM passes = slower.** All local; the existing elapsed timer + progress bar
  + stop button cover the UX. Pass count is a config knob.

---

## 8. Definition of done (per the Final goal)

The upgrade is "done" for the specialist-coach role when, for a typical clip, the
analysis: (a) talks about *specific strokes* with *timestamps* the user can verify;
(b) is backed by *dynamic* biomechanic numbers, not just postures; (c) records those
numbers as a *time series* so progress is queryable; and (d) exposes all of it
through `/report` in a stable, structured shape the future Head Coach can read
without re-running anything.
