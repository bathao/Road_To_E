// Journal tab (📔): the daily table-tennis diary — replaces the grid's
// Coach & Recap row (2026-08-20) over the SAME session-note store, so every
// old advice/drill/recap shows up as the journal of its day automatically.
// Layout follows the big journaling apps (Day One / Journey): a centered
// column, a "today's page" composer on top, then a month-grouped timeline
// with a date block per day. Coach reminders (advice/drill/recap) only on
// days with a Train-with-Coach session; 💡 lessons any day. Advice keeps its
// done-lifecycle; the AI coach reads lessons as their own bundle section.
import { useEffect, useState } from "react";
import { useLoad, useMutate } from "../../shared/useApi";
import { toIso } from "../../shared/dates";
import Seg from "../../shared/ui/Seg";
import { trackerApi } from "../daily-tracker/api";
import type { JournalDay, SessionNoteKind } from "../daily-tracker/types";
import DayCard from "./components/DayCard";
import RememberPanel from "./components/RememberPanel";
import TrackingPanel from "./components/TrackingPanel";
import RichArea from "./RichArea";
import { renderMarkup } from "./markup";

const PAGE = 30;

const longDate = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

// NOTE: deliberately NOT shared/dates.monthLabel — the timeline wants the
// full "August 2026" (that helper abbreviates to "Aug 2026").
const monthTitle = (iso: string) =>
  new Date(iso + "T00:00:00").toLocaleDateString("en-GB", {
    month: "long",
    year: "numeric",
  });

export default function Journal() {
  const todayIso = toIso(new Date());
  const { run, error, busy, clearError } = useMutate();

  const { data: tags } = useLoad(() => trackerApi.getSessionNoteTags(), []);

  // Composer target day (defaults to today; the coach block gates on it).
  const [dateIso, setDateIso] = useState(todayIso);
  const { data: day, reload: reloadDay } = useLoad(
    () => trackerApi.getJournalDay(dateIso),
    [dateIso]
  );

  // Timeline: first page via useLoad; older pages accumulate in `extra`.
  // Any mutation resets the extras and reloads page one (older days can't
  // change from the composer, and duplicates would be worse than a re-page).
  const { data: firstPage, reload: reloadDays } = useLoad(
    () => trackerApi.getJournalDays(PAGE),
    []
  );
  const [extra, setExtra] = useState<JournalDay[]>([]);
  const [extraHasMore, setExtraHasMore] = useState<boolean | null>(null);
  const days = [...(firstPage?.days ?? []), ...extra];
  const hasMore = extraHasMore ?? firstPage?.has_more ?? false;

  // Month groups for the timeline separators (days arrive newest first).
  const months: { label: string; days: JournalDay[] }[] = [];
  for (const d of days) {
    const label = monthTitle(d.date);
    const last = months[months.length - 1];
    if (last && last.label === label) last.days.push(d);
    else months.push({ label, days: [d] });
  }

  const loadMore = async () => {
    const last = days[days.length - 1];
    if (!last) return;
    const out = await run(() => trackerApi.getJournalDays(PAGE, last.date));
    if (out === undefined) return;
    setExtra((e) => [...e, ...out.days]);
    setExtraHasMore(out.has_more);
  };

  const refresh = () => {
    setExtra([]);
    setExtraHasMore(null);
    reloadDays();
    reloadDay();
  };

  // ---- composer: a LOCAL draft of the WHOLE day (user 2026-08-20: write
  // the full day first, nothing saved until one "Save day" press). Coach
  // lines stay line-based because advice needs its own done-lifecycle row;
  // the lessons textarea saves as ONE multi-line lesson entry. ----
  interface DraftLine {
    kind: SessionNoteKind;
    tags: string[];
    text: string;
  }
  const [coachKind, setCoachKind] = useState<SessionNoteKind>("advice");
  const [coachTags, setCoachTags] = useState<string[]>([]);
  const [coachText, setCoachText] = useState("");
  const [draftLines, setDraftLines] = useState<DraftLine[]>([]);
  const [lessonText, setLessonText] = useState("");
  // Matches area: per-match note drafts, seeded from the loaded day (and
  // re-seeded after every save/reload — the server copy wins).
  const [matchNotes, setMatchNotes] = useState<Record<number, string>>({});
  useEffect(() => {
    setMatchNotes(
      Object.fromEntries((day?.matches ?? []).map((m) => [m.id, m.note]))
    );
  }, [day]);
  const changedNotes = (day?.matches ?? []).filter(
    (m) => (matchNotes[m.id] ?? "") !== m.note
  );
  // Text still sitting in the coach box counts as part of the draft — Save
  // day must NEVER discard it (it did once, 2026-08-21, and the entry was
  // unrecoverable: "＋ Line" is optional, not a prerequisite).
  const pendingCoach =
    day?.has_coach_session && coachText.trim()
      ? [{ kind: coachKind, tags: coachTags, text: coachText.trim() }]
      : [];
  const draftEmpty =
    draftLines.length === 0 &&
    pendingCoach.length === 0 &&
    !lessonText.trim() &&
    changedNotes.length === 0;

  const addDraftLine = () => {
    if (!coachText.trim()) return;
    setDraftLines((d) => [
      ...d,
      { kind: coachKind, tags: coachTags, text: coachText.trim() },
    ]);
    setCoachText("");
    setCoachTags([]);
  };

  const saveDay = async () => {
    if (busy || draftEmpty) return;
    const ok = await run(async () => {
      for (const l of [...draftLines, ...pendingCoach]) {
        await trackerApi.createSessionNote({
          date: dateIso,
          kind: l.kind,
          tags: l.tags,
          text: l.text,
        });
      }
      if (lessonText.trim()) {
        await trackerApi.createSessionNote({
          date: dateIso,
          kind: "lesson",
          tags: [],
          text: lessonText.trim(),
        });
      }
      for (const m of changedNotes) {
        await trackerApi.setMatchNote(m.id, (matchNotes[m.id] ?? "").trim());
      }
      return true;
    });
    if (ok === undefined) return; // failed → keep the draft to adjust
    setDraftLines([]);
    setLessonText("");
    setCoachText("");
    setCoachTags([]);
    refresh();
  };

  const tagLabel = (key: string) => tags?.find((t) => t.key === key)?.label ?? key;
  const drillCount = (day?.items ?? []).filter((n) => n.kind === "drill").length;

  return (
    <div className="tab-journal">
      {/* Three columns: the Remember board (user 2026-09-24, standing
          reminders that never scroll away) on the LEFT, the diary (composer
          + timeline) in the middle, the Tracking board (user 2026-08-24) on
          the right. */}
      <RememberPanel />
      <div className="jr-main">
      <header className="jr-head">
        <h1>📔 Journal</h1>
        <p className="jr-sub">Your table-tennis diary — the AI coach reads all of it.</p>
      </header>

      {error && (
        <div className="error-banner" onClick={clearError}>
          ⚠ {error}
        </div>
      )}

      <section className="jr-composer">
        <div className="jr-composer-head">
          <div className="jr-composer-date">
            <span className="jr-composer-day">
              {dateIso === todayIso ? "Today" : longDate(dateIso)}
            </span>
            {dateIso === todayIso && (
              <span className="jr-composer-full">{longDate(dateIso)}</span>
            )}
          </div>
          <input
            type="date"
            className="jr-datepick"
            title="Write for another day"
            value={dateIso}
            max={todayIso}
            onChange={(e) => setDateIso(e.target.value || todayIso)}
          />
        </div>

        {day?.has_coach_session ? (
          <div className="jr-block">
            <div className="jr-block-head">
              🧑‍🏫 Lesson
              {day.coaches.length > 0 && (
                <span className="jr-block-sub">
                  {" "}— session with Coach {day.coaches.join(" + Coach ")}
                </span>
              )}
            </div>
            {draftLines.length > 0 && (
              <div className="jr-draft-list">
                {draftLines.map((l, i) => (
                  <div key={i} className="jr-item">
                    <span className="jr-item-icon">
                      {l.kind === "advice" ? "🧑‍🏫" : l.kind === "drill" ? "🏓" : "📋"}
                    </span>
                    <span className="jr-item-text">
                      {renderMarkup(l.text)}
                      {l.tags.map((t) => (
                        <span key={t} className="jr-tag">
                          {tagLabel(t)}
                        </span>
                      ))}
                    </span>
                    <button
                      className="jr-act jr-act-del"
                      title="Remove from the draft"
                      onClick={() =>
                        setDraftLines((d) => d.filter((_, j) => j !== i))
                      }
                    >
                      ✕
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="jr-coach-controls">
              <Seg
                options={[
                  ["advice", "Coach said"],
                  ["drill", "Drill"],
                  ["recap", "Recap"],
                ]}
                value={coachKind}
                onChange={setCoachKind}
              />
              <div className="jr-tag-row">
                {(tags ?? []).map((t) => {
                  const on = coachTags.includes(t.key);
                  return (
                    <button
                      key={t.key}
                      className={`jr-tag jr-tag-btn${on ? " on" : ""}`}
                      onClick={() =>
                        setCoachTags((d) =>
                          on ? d.filter((k) => k !== t.key) : [...d, t.key]
                        )
                      }
                    >
                      {t.label}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="jr-input-row">
              <RichArea
                className="jr-coach-input"
                value={coachText}
                onChange={setCoachText}
                placeholder={
                  coachKind === "advice"
                    ? "What did the coach ask you to work on?"
                    : coachKind === "drill"
                      ? `Drill ${drillCount + draftLines.filter((l) => l.kind === "drill").length + 1} — what did you practice?`
                      : "How did the session go overall?"
                }
              />
              <button
                className="btn"
                disabled={!coachText.trim()}
                onClick={addDraftLine}
                title="Add this line to the day's draft (nothing saves yet)"
              >
                ＋ Line
              </button>
            </div>
          </div>
        ) : (
          day && (
            <p className="jr-gate-hint">
              No Train-with-Coach session on this day — log one in the Daily
              Tracker to add coach reminders.
            </p>
          )
        )}

        {day && (
          <div className="jr-block">
            <div className="jr-block-head">
              🏓 Matches
              <span className="jr-block-sub"> — one note per opponent of the day</span>
            </div>
            {day.matches.length === 0 ? (
              <p className="jr-gate-hint jr-gate-inline">
                No matches logged on this day — enter them in the Daily
                Tracker and your notes go here.
              </p>
            ) : (
              day.matches.map((m) => (
                <div key={m.id} className="jr-match">
                  <div className="jr-match-label">{m.label}</div>
                  <RichArea
                    className="jr-match-input"
                    value={matchNotes[m.id] ?? ""}
                    onChange={(v) =>
                      setMatchNotes((d) => ({ ...d, [m.id]: v }))
                    }
                    placeholder="How did it go vs this opponent? What to remember?"
                  />
                </div>
              ))
            )}
          </div>
        )}

        <div className="jr-block">
          <div className="jr-block-head">
            📝 Notes
            <span className="jr-block-sub"> — optional, anything else from the day</span>
          </div>
          <RichArea
            className="jr-lesson-input"
            value={lessonText}
            onChange={setLessonText}
            placeholder="Write freely — everything this day taught you."
          />
        </div>

        <div className="jr-save-row">
          <span className="jr-draft-hint">
            {draftEmpty
              ? "Nothing is saved until you press Save day."
              : "Draft in progress — not saved yet."}
          </span>
          <button
            className="btn primary jr-save-day"
            disabled={busy || draftEmpty}
            onClick={() => void saveDay()}
          >
            💾 Save day
          </button>
        </div>
      </section>

      <div className="jr-timeline">
        {months.map((m) => (
          <div key={m.label} className="jr-month">
            <div className="jr-month-label">{m.label}</div>
            {m.days.map((d) => (
              <DayCard
                key={d.date}
                day={d}
                todayIso={todayIso}
                tagLabel={tagLabel}
                onChanged={refresh}
              />
            ))}
          </div>
        ))}
        {days.length === 0 && (
          <p className="jr-empty">No entries yet — today's page is waiting. ✍️</p>
        )}
        {hasMore && (
          <button className="btn jr-more" disabled={busy} onClick={() => void loadMore()}>
            Load older days…
          </button>
        )}
      </div>
      </div>

      <TrackingPanel />
    </div>
  );
}
