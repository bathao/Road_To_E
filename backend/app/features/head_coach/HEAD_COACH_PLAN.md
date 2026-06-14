# Head Coach ("HLV trưởng") — Tier-2 design

The north-star module. A single, **strict personal coach** for one player,
Nguyễn Bá Thảo. Persona (agreed with the user): a professional table-tennis
coach who looks after one special athlete, knows his stats, and is **demanding**
— tracks progress, pushes him to train more, log more playing hours, play more
matches (singles / doubles / vs-pips), sharpen tactics, and proposes concrete
in-match tactics to follow.

## Principle: consumer, not collector

The Head Coach **reads** what the Tier-1 specialists wrote and synthesises a
verdict. It never re-collects or re-analyses. All four data sources are already
machine-readable; it calls their service functions **in-process** (no HTTP):

| Source | In-process call | Provides |
|---|---|---|
| Video Analysis | `video_service.build_report(db)` | 9-aspect skill ledger (rating/status/assessment/priority + evidence), strengths, weaknesses, metric trends |
| Training Center | `training_service.report(db)` | level, adherence (7/30d, days-since-last), volume by muscle group, streak, intensity_bias |
| Daily / Match | `tracker_service.build_stats(db, from, to)` | days trained / physical, minutes by category, win-rate singles / doubles / overall / vs-pips |
| Tactical Playbook | `playbook_service.list_tactics(db)` | the player's known tactics & tendencies |

Only **accepted** video findings reach it (Video Analysis already gates), so the
brain consumes confirmed data, not raw guesses.

## AI model

Text-only reasoning — **no VLM**. `settings.HEAD_COACH_MODEL` (default
`qwen3:14b`, already pulled, fits the 16GB GPU with room for a 16k context, has a
thinking mode). Called like `analyzer.synthesize_skills`: `httpx.post` to Ollama
`/api/chat` with a JSON-schema `format`, low temperature, Vietnamese prompt.
Swap the knob for a larger reasoner (`gpt-oss:20b`, `qwen3:30b-a3b`) if needed.

## Output (the verdict)

Structured JSON → `AssessmentOut`:
- `overall_assessment` — 3-5 câu, problem-first, no flattery (a demanding coach).
- `top_priorities[]` — ranked, each with `title`, `why`, `source` chip.
- `directives[]` — concrete "tăng cường" orders: train more / more playing hours
  / more matches (singles, doubles, vs-pips) / sharpen a skill, each with a
  measurable target and the data that triggered it.
- `tactics[]` — in-match tactical suggestions to follow.
- `week_plan[]` — a concrete week, each day tied to a Training-Center day-type
  and/or a drill drawn from a weakness.
- `watch_items[]` — warnings (stale data, low match volume, knee safety).

Persisted as a **snapshot** in `hc_assessment` (latest = current verdict; the
generate call replaces/appends). Generated **on-demand** (a button), not on every
load — one local-LLM call is slow and the inputs change slowly.

## Phasing

- **Phase 1 (this build):** gather bundle → synthesize → persist latest snapshot
  → display tab. On-demand generate + regenerate. Prove the verdict is sharp.
- **Phase 2:** review/confirm gate + history of snapshots (consistent with the
  project's accepted-only contract).
- **Phase 3 (optional):** write-back — drive Training-Center prescriptions, push
  suggested tactics into the Playbook. Cross-tab actions.

## Honesty

Stamp source freshness; warn when video clips are stale or match volume is thin.
Not medical advice (grade-1 knee OA) — never prescribe deep squats / jumping.
