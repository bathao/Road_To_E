# Video Analysis → Text Analysis (date-stamped, practice/match) — Plan

> Status: **implemented & verified (current).** Local-VLM pipeline abandoned;
> this is now a text intake on the shared `qwen3:14b` model.
>
> **What works now:**
> - **Intake tab "Phân tích kỹ thuật"** (📝) is *pure*: paste a cloud analysis,
>   tagged with **date** + **setting** (🏓 Tập / 🔥 Đấu) → parses into findings,
>   **auto-accepts** them (no review gate), and **auto-rebuilds the skill ledger**.
>   No profile/skills shown here; single column (PasteForm + ReportList + ReviewPanel).
> - **Full practice/match separation** (§10.A): `va_skill` keyed on
>   `(aspect, setting)`, `va_skill_snapshot` carries `setting`; `regenerate_skills`
>   runs once per setting; separate rating + history + the "🆚 Tập vs Đấu" contrast.
> - **The living profile lives in the Profile tab** (§8): editable basics + AI
>   summary (`ProfilePanel`), the **radar + bars overview** (per-setting toggle —
>   the original good-looking visual, kept), the detailed `SkillBoard` (edit /
>   assessment / evidence / trend / contrast), and the `TraitBoard` knowledge base
>   (manual add/delete), plus competitive / training / Training-Center snapshots.
> - **Head Coach** reads per-setting ratings + history + the practice-vs-match gap
>   and is prompted to prescribe match-specific fixes.
> - Tab renamed → "Phân tích kỹ thuật" 📝. Old media `data/videos` + `profile_refs`
>   deleted; `requirements.txt` trimmed of the CV stack.
>
> Verified: backend migration + per-setting regenerate + auto-rebuild-on-paste
> (stubbed LLM: forehand practice 8 / match 3, 18 ledger rows); frontend builds.
>
> **Still not done:** the **live Ollama calls** were only exercised with stubs —
> run the real model once to sanity-check output quality (§10.B.1). Not committed yet.

## 1. Why the change

The local vision-language model (`qwen3-vl:8b`) + pose/ball/identity CV pipeline
did not produce useful analysis. The user now runs video analysis on a stronger
**cloud** model elsewhere and **copies the text output** into this tab. So the
tab's job shrinks to what it was always good at: **parse text → structured
findings → update the database**, on the **same local text model the Head Coach
uses** (`qwen3:14b`). No video is processed here anymore.

## 2. The two halves (what changed, what stayed)

- **Input half — REPLACED.** Upload clip → identity (ArcFace/body re-ID) → local
  VLM + pose + ball → findings. All deleted: `analyzer.py` (VLM), `ball.py`,
  `identity.py`, `table_roi.py`, pose/metrics, the detect/confirm/identify flow,
  the reference-image gallery, and the `onnxruntime`/`ultralytics`/face deps.
- **Output half — KEPT.** Findings (`VATrait`) → skill ledger (`VASkill`) →
  profile summaries (`VAProfile`) → `build_report` → consumed by the Head Coach.
  This already ran on the text model.

New input: a **paste box + setting + date picker**. Paste cloud text, tag it →
text model extracts findings → **auto-accepted** (the user already curated the
text before pasting, so there is **no review gate**; findings can still be edited
or removed afterwards) → skills/profile regenerate → report feeds the Coach.

## 2b. Practice vs match (the in-match gap)

Each report is tagged with a **setting**: `practice` (tập luyện / khởi động) or
`match` (thi đấu trận thật). The player performs technique well in practice but
worse under match pressure, and wants the Coach to see this clearly.

- `VAReport.setting` — user picks when pasting (default `practice`).
- Findings inherit the setting via their report; `findings_timeline` carries it.
- `build_report.practice_vs_match` — per-aspect counts of strength/weakness split
  by setting (+ sample texts), so the gap is explicit.
- **CURRENT (interim):** the skill ledger is still **one rating per aspect**, fed
  all findings with the setting tag and told to rate by **match** performance
  (good-in-practice-bad-in-match ⇒ low rating + high priority + a note). The
  practice-vs-match split is only a **finding contrast** (`practice_vs_match`).
- **NEXT (§10): full separation** — a separate rating + history per aspect for
  practice and for match.
- The Head Coach bundle renders a "CHÊNH LỆCH TẬP vs ĐẤU" block and the prompt
  tells it to prescribe match-specific measures (pressure drills, situational
  practice, mentality) — not just plain technique work.

## 3. Date dimension

Every analysis is **anchored to a date the user inputs** (the day the footage is
from), so the Coach can track development over time:

- `VAReport.analysis_date` — user-entered, defaults to today, **backdatable**,
  **never in the future** (same rule as Training Center's `done_on`).
- Each `VATrait` is dated via its source report (`source_report_id`).
- **Skill history** (`VASkillSnapshot`): each time the skill ledger is rebuilt,
  one dated point `(analysis_date, aspect, rating, status)` is written
  (upserted per date+aspect). This is the rating-over-time series.
- This replaces the old pose-derived `metric_trends` as the Coach's progress
  signal — now progress is **technical/skill** trend, not pose numbers.

## 4. Data model

```
VAReport (new)
  id
  analysis_date  DATE     ← user input; default today; backdatable; not future
  setting        STR      ← practice | match (the in-match gap)
  title          STR
  context        STR      ← optional finer steer for the parser
  source_text    TEXT     ← the pasted cloud analysis
  model          STR      ← which local model parsed it
  status         STR      parsing → reviewed | error   (auto-accept: no review gate)
  error_msg      TEXT?
  reviewed_at    DATETIME?
  created_at     DATETIME

VATrait (changed)
  …aspect, polarity, text, ai_text, confidence, status, reviewed_at, created_at
  source_report_id  → FK va_report (NULL = manual entry)
  (dropped from the model: t_ref, evidence_json — video-only; columns left dead in DB)

VASkillSnapshot (new)
  id, analysis_date DATE, aspect STR, rating INT?, status STR,
  report_id INT? (FK va_report), created_at

VAProfile, VASkill — unchanged.
Dropped tables: va_clip, va_analysis, va_metric, va_profile_image.
```

**Migration (additive + drop dead tables).** The DB had 0 accepted findings and 0
rated skills, so nothing valuable is lost. `seed.migrate()` drops the four video
tables, adds `source_report_id` to `va_trait` and `setting` to `va_report`;
`create_all` makes the new tables. `VAProfile` basics + the empty `VASkill`
ledger are preserved.

## 5. Parsing — shared model with the Coach

- `text_synth.extract_findings(text, basics, context)` → one `qwen3:14b` call
  (JSON-schema output) returning `[{aspect, polarity, text, confidence}]`.
- Runs in a **background task** (`parse_report`) so the UI stays responsive;
  status `parsing` → `reviewed` (findings auto-accepted). Frontend polls while any
  report parses, refreshing the knowledge base when it finishes.
- `text_synth` also hosts `synthesize_profile`, `synthesize_skills`,
  `check_models` (moved out of the deleted `analyzer.py`).
- `settings.TEXT_MODEL` is the single shared constant; `HEAD_COACH_MODEL = TEXT_MODEL`.

## 6. API (`/api/video`)

Removed: clips, identity, profile-images, health/model (VLM), browse, frame,
crop-reference, video/preview/evidence streams.

Kept: profile (+regenerate-summary), traits CRUD, skills (+regenerate), report.

New:
- `POST /reports`  — `{source_text, analysis_date, setting, title, context}` → create + kick off parse.
- `GET  /reports`  — list (newest first, by analysis_date).
- `GET  /reports/{id}` — detail + its findings.
- `POST /reports/{id}/review` — optional: edit/remove findings (no longer a gate).
- `DELETE /reports/{id}` — delete a report (cascades its findings).

`GET /report` (player report) gains `skill_history`, `findings_timeline` (both
dated, setting-tagged), and `practice_vs_match`; drops `metric_trends`.
`clips_reviewed` → `reports_reviewed`.

## 7. Head Coach integration

`gather_bundle` reads `skill_history` + `findings_timeline` + `practice_vs_match`.
`_bundle_to_text` renders a **progress** block (first vs latest rating per
aspect), a **CHÊNH LỆCH TẬP vs ĐẤU** block, and recent dated findings tagged
TẬP/ĐẤU. The prompt asks the Coach to judge improvement/stagnation over time and
to prescribe match-specific fixes when the practice→match gap is large.

## 8. Frontend

**Tab "Phân tích kỹ thuật"** (`tabs/video-analysis/`, label renamed from "Video
Analysis", icon 📝) is now a **pure intake**, single column — no profile/skills/
findings display:
- `PasteForm` — setting picker (🏓 Tập / 🔥 Đấu) + date picker (Hôm nay / Hôm qua /
  lịch, max = today) + textarea; findings auto-save + auto-rebuild ledger.
- `ReportList` (by date, setting chip) + `ReviewPanel` (view findings; edit/remove
  optional, not a gate).
- Deleted: `UploadForm`, `ClipList`, `AnalysisDetail`, `BoxAnnotator`,
  `AnalysisProgress`.

**The living profile moved to the Profile tab** (`tabs/profile/`). It now composes
the components that used to sit in the analysis tab's left column:
- `ProfilePanel` — editable basics + AI summary (overall + serve/footwork/posture/
  strengths/weaknesses) + "Tổng hợp lại từ nhận xét".
- `SkillRadar` (visual, per-setting toggle) + `SkillBoard` (per-(aspect,setting)
  ratings, edit, assessment, evidence, skill-history trend, "🆚 Tập vs Đấu" contrast,
  regenerate).
- `TraitBoard` — confirmed findings (knowledge base) + manual add/delete (the only
  place to add a finding by hand now).
- Plus its own competitive / training / Training-Center snapshots.
- (`ProfilePanel` lost the image gallery; Profile avatar is the 🏓 placeholder.)

## 9. Done / verified

- Backend: app import OK, migration drops old tables + creates `va_report`/
  `va_skill_snapshot`, `build_report` + coach bundle render (stubbed LLM); the
  `practice` vs `match` contrast computes correctly; test data cleaned out.
- Frontend: `tsc --noEmit` clean, `npm run build` OK.
- `requirements.txt` trimmed (opencv/mediapipe/ultralytics/insightface/onnxruntime/
  scikit-image/python-multipart removed).

## 10. Next session (TODO — "tối làm tiếp")

### 10.A — FULL practice/match separation — ✅ DONE

Implemented exactly as designed below: each aspect now has **two independent
ratings + histories** (practice + match). `va_skill` keyed on `(aspect, setting)`
(migration drops & recreates it once); `regenerate_skills` calls
`synthesize_skills(..., setting=…)` once per setting; `build_report`/`skill_history`
carry `setting`; `PUT /skills/{setting}/{aspect}`; SkillBoard shows Tập|Đấu rows;
Profile radar has a Tập/Đấu toggle; Head Coach renders per-setting ratings + a
practice-vs-match block. Original design kept below for reference.

**1. Data model** (`models.py`)
- `VASkill`: add `setting` column (`practice` | `match`). The current uniqueness
  is on `aspect`; change it to **composite unique `(aspect, setting)`** → two rows
  per aspect.
- `VASkillSnapshot`: add `setting` column. Upsert key becomes
  `(analysis_date, aspect, setting)`.

**2. Migration** (`seed.py`)
- `va_skill` currently holds 9 neutral/unrated scaffold rows (no real data), and
  its unique index is on `aspect` — SQLite can't alter that in place. Simplest:
  **`DROP TABLE va_skill`** in `migrate()` and let `create_all` rebuild it with the
  composite unique; then `seed_profile` seeds **two rows per `SKILL_ASPECT`**
  (practice + match), all neutral. (Safe: no rated data lost. Confirm with a count
  first — if any `rating IS NOT NULL`, back up before dropping.)
- `va_skill_snapshot` is empty → drop & recreate too (adds the `setting` column),
  or just `ALTER TABLE ... ADD COLUMN setting`.

**3. Service** (`service.py`)
- `list_skills` → return both settings; helper `skills_by_setting(db)`.
- `regenerate_skills`: split accepted findings by setting and call
  `synthesize_skills` **twice** (practice-only findings → write practice rows;
  match-only → match rows). A setting with no findings → leave its rows neutral
  (skip the call). After each, write a `VASkillSnapshot` for that
  `(date, aspect, setting)`.
- `update_skill`: key by `(aspect, setting)`.
- `skill_history`: group by `(aspect, setting)` → two series per aspect.
- `build_report`: expose skills + skill_history per setting. Keep
  `practice_vs_match` (finding counts) as a complement. Decide the `skills` shape:
  either `skills_practice` / `skills_match` lists, or one list with a `setting`
  field (preferred — less schema churn; FE groups).

**4. Text model** (`text_synth.py`)
- `synthesize_skills(basics, findings_by_aspect, setting)`: add a `setting` param;
  drop the "rate by match" cross-setting instruction and instead rate **this
  setting's** level from this setting's findings. (Call it once per setting.)

**5. API** (`router.py`)
- `PUT /skills/{setting}/{aspect}` (was `/skills/{aspect}`).
- `/report` and `/skills` payloads gain `setting`.

**6. Schemas** (`schemas.py`)
- `SkillOut`, `SkillReportItem`, `SkillHistory` gain `setting`.

**7. Frontend**
- `types.ts`/`labels.ts`: `setting` on Skill/SkillHistory.
- `SkillBoard`: render two ratings per aspect (a **Tập** column and an **Đấu**
  column, each with bar + status + assessment), or a setting toggle. Edit writes
  to the right `(aspect, setting)`.
- `Profile` tab `SkillRadar`: overlay two radars (practice vs match) or a toggle.
- `api.ts`: `updateSkill(setting, aspect, …)`; regenerate triggers both settings.

**8. Head Coach** (`head_coach/service.py` + `prompt.py`)
- `gather_bundle`: include both rating sets per aspect (practice vs match) +
  per-setting history. `_bundle_to_text`: a line like
  `Phải tay — Tập 7/10 vs Đấu 4/10`. Prompt: act on the gap explicitly.

**Edge cases / notes**
- Aspect with findings in only one setting → only that setting gets a rating; the
  other stays neutral/`—` (don't fabricate).
- Profile summary text can stay single (overall); the split is for ratings.
- Verify: paste 1 practice + 1 match report, regenerate, confirm two distinct
  ratings + two history series + radar overlay + coach line.

### 10.B — Smaller follow-ups
1. **Live LLM check** — STILL TODO. Ollama up + `qwen3:14b` pulled; paste a real
   practice and a real match analysis; confirm `extract_findings` + both
   `synthesize_skills` calls produce sane output. Tune prompts. (All paths above
   only stub-tested.)
2. **Tab rename — ✅ DONE.** Registry label is now "Phân tích kỹ thuật" 📝
   (id `video-analysis` unchanged).
3. **Auto-regenerate after paste — ✅ DONE.** `parse_report` now rebuilds the skill
   ledger (per setting) automatically after saving findings; a model failure is
   non-fatal (findings stay saved). The tab polls skills while parsing. The manual
   "Cập nhật hồ sơ kỹ năng" button still exists as a fallback.
4. **Cleanup — partial.** Deleted `data/videos` (~192M, gitignored clips+evidence)
   and `data/profile_refs` (auto-gen crops) + the orphan `proposed` trait.
   **KEPT (real/valuable user data — ask before deleting):** `data/identity/me/`
   (40 original portrait photos, ~190M) and `data/models/roi_seg.pt` (fine-tuned
   model).
5. **Commit** — nothing committed yet; commit when the user asks.
