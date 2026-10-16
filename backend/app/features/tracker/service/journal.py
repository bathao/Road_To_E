"""Session notes (coach advice / drills / recaps / lessons) and the journal timeline.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session, selectinload

from app.core.errors import BadRequest, NotFound
from app.features.tracker import schemas
from app.features.tracker.models import (
    Activity,
    Category,
    Coach,
    Match,
    SessionNote,
)

# Fixed tag set for journal coach items. (key, English label) — same pattern
# as PHYSICAL_ITEMS; unknown keys are dropped on write, never rejected.
SESSION_NOTE_TAGS: list[tuple[str, str]] = [
    ("serve", "Serve"),
    ("receive", "Receive"),
    ("fh_topspin", "FH Topspin"),
    ("fh_backspin", "FH Backspin"),
    ("fh_push", "FH Push"),
    ("bh_topspin", "BH Topspin"),
    ("bh_backspin", "BH Backspin"),
    ("bh_push", "BH Push"),
    ("short_touch", "Short Touch"),
    ("footwork", "Footwork"),
    ("tactics", "Tactics"),
    ("physical", "Physical"),
    ("mental", "Mental"),
]


SESSION_NOTE_TAG_LABELS = dict(SESSION_NOTE_TAGS)


SN_KIND_ADVICE = "advice"  # something the coach told me to work on


SN_KIND_DRILL = "drill"  # one concrete exercise of the session (auto-numbered)


SN_KIND_RECAP = "recap"  # what the session covered overall


# lesson = the player's own takeaway of the day (Journal tab 2026-08-20) —
# allowed on ANY day (no coach-session gate) and has no done-lifecycle.
SN_KIND_LESSON = "lesson"


def clean_session_tags(tags: list[str]) -> list[str]:
    """Keep known tag keys only, deduped, in the canonical SESSION_NOTE_TAGS
    order (so two items tagged the same way always render the same way)."""
    wanted = set(tags or [])
    return [key for key, _ in SESSION_NOTE_TAGS if key in wanted]


def session_note_to_out(n: SessionNote) -> schemas.SessionNoteOut:
    return schemas.SessionNoteOut(
        id=n.id,
        date=n.date,
        kind=n.kind,
        tags=[t for t in (n.tags or "").split(",") if t],
        text=n.text,
        is_done=bool(n.is_done),
    )


def has_coach_session(db: Session, d: dt.date) -> bool:
    """Whether the day has a Train-with-Coach activity with actual minutes."""
    return (
        db.query(Activity.id)
        .join(Category, Category.id == Activity.category_id)
        .filter(
            Category.key == "train_with_coach",
            Activity.date == d,
            Activity.duration_minutes > 0,
        )
        .first()
        is not None
    )


def create_session_note(db: Session, payload: schemas.SessionNoteIn) -> SessionNote:
    """Add a Journal item. Coach items (advice/drill/recap) are only allowed
    on days that actually have a coach session — they are a record of those
    sessions. A `lesson` (the player's own takeaway, Journal tab 2026-08-20)
    is welcome on ANY day."""
    text_ = (payload.text or "").strip()
    if not text_:
        raise BadRequest("Text is required")
    if payload.kind != SN_KIND_LESSON and not has_coach_session(db, payload.date):
        raise BadRequest("No Train with Coach session on this day — log it first")
    n = SessionNote(
        date=payload.date,
        kind=payload.kind,
        tags=",".join(clean_session_tags(payload.tags)),
        text=text_,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return n


def update_session_note(
    db: Session, note_id: int, payload: schemas.SessionNoteUpdate
) -> SessionNote:
    """Partial update. Deliberately NOT re-gated on has_coach_session: the item
    was valid when created, and it must stay manageable (esp. ticking advice
    done) even if the coach activity was edited away later."""
    n = db.get(SessionNote, note_id)
    if n is None:
        raise NotFound(f"session note {note_id} not found")
    if payload.text is not None:
        text_ = payload.text.strip()
        if not text_:
            raise BadRequest("Text cannot be empty — delete the item instead")
        n.text = text_
    if payload.tags is not None:
        n.tags = ",".join(clean_session_tags(payload.tags))
    if payload.is_done is not None and n.kind == SN_KIND_ADVICE:
        n.is_done = payload.is_done
    db.commit()
    db.refresh(n)
    return n


def delete_session_note(db: Session, note_id: int) -> bool:
    n = db.get(SessionNote, note_id)
    if n is None:
        return False
    db.delete(n)
    db.commit()
    return True


def list_active_advice(db: Session) -> list[SessionNote]:
    """Every advice item not yet marked done, oldest first. UI-less since
    the checklist was dropped 2026-08-21 — only the AI bundle reads it."""
    return (
        db.query(SessionNote)
        .filter(SessionNote.kind == SN_KIND_ADVICE, SessionNote.is_done.is_(False))
        .order_by(SessionNote.date, SessionNote.id)
        .all()
    )


# ---------------------------------------------------------------- journal
def _journal_coach_names(db: Session, dates: list[dt.date]) -> dict[str, list[str]]:
    """iso date -> that day's Train-with-Coach coach names (deduped, entry
    order). coach_id NULL = the package coach (same convention as the package
    math); no package coach seeded and NULL → the day just shows no name."""
    if not dates:
        return {}
    coach_cat = db.query(Category).filter(Category.key == "train_with_coach").first()
    if coach_cat is None:
        return {}
    names = {c.id: c.name for c in db.query(Coach).all()}
    package = next(
        (c.name for c in db.query(Coach).filter(Coach.counts_package.is_(True))
         .order_by(Coach.id).all()),
        None,
    )
    out: dict[str, list[str]] = {}
    acts = (
        db.query(Activity)
        .filter(
            Activity.category_id == coach_cat.id,
            Activity.date.in_(dates),
            Activity.duration_minutes > 0,
        )
        .order_by(Activity.id)
        .all()
    )
    for a in acts:
        name = names.get(a.coach_id) if a.coach_id else package
        day = out.setdefault(a.date.isoformat(), [])
        if name and name not in day:
            day.append(name)
    return out


def _journal_result_token(m: Match) -> str:
    """One match's result inside a group label: 'W 3-2', 'L 1-3 (receive 2)'."""
    if m.my_sets == m.opp_sets:
        res = f"T {m.my_sets}-{m.opp_sets}"
    else:
        res = f"{'W' if m.my_sets > m.opp_sets else 'L'} {m.my_sets}-{m.opp_sets}"
    if m.handicap:
        spec = m.handicap_pattern or str(abs(m.handicap))
        res += f" ({'give' if m.handicap > 0 else 'receive'} {spec})"
    return res


def _group_day_matches(matches: list[Match]) -> list[list[Match]]:
    """One journal note covers ALL of a day's matches vs the same opponent
    (user 2026-08-21) — group by opponent(s) + partner, first-played order."""
    groups: dict[tuple, list[Match]] = {}
    for m in matches:
        key = (
            tuple(sorted(i for i in (m.opponent_id, m.opponent2_id) if i)),
            m.partner_id,
        )
        groups.setdefault(key, []).append(m)
    return list(groups.values())


def _journal_group_out(members: list[Match]) -> schemas.JournalMatchOut:
    """Group → API shape. `id` is the note-holder: the first noted match if
    any (so edits round-trip to where the note lives), else the first played.
    'vs Anh Tuấn — W 3-2, W 3-1 (receive 2)'."""
    first = members[0]
    results = ", ".join(_journal_result_token(m) for m in members)
    opps = " & ".join(p.name for p in (first.opponent, first.opponent2) if p is not None)
    label = f"vs {opps}" if opps else results
    if first.partner is not None:
        label += f" (with {first.partner.name})"
    if opps:
        label += f" — {results}"
    primary = next((m for m in members if m.note), first)
    return schemas.JournalMatchOut(id=primary.id, label=label, note=primary.note or "")


def _journal_day_match_rows(db: Session, dates: list[dt.date]) -> dict[dt.date, list[Match]]:
    if not dates:
        return {}
    rows = (
        db.query(Match)
        .filter(Match.is_nonplaying == False, Match.date.in_(dates))  # noqa: E712
        .options(
            selectinload(Match.opponent),
            selectinload(Match.opponent2),
            selectinload(Match.partner),
        )
        .order_by(Match.date, Match.order_index, Match.id)
        .all()
    )
    out: dict[dt.date, list[Match]] = {}
    for m in rows:
        out.setdefault(m.date, []).append(m)
    return out


def _journal_matches(
    db: Session, dates: list[dt.date], noted_only: bool
) -> dict[dt.date, list[schemas.JournalMatchOut]]:
    """The Matches area rides tracker_match directly — a match note IS the
    'lưu ý' about that day's opponent (and the Tactics h2h context reads it).
    Grouping happens here so the label always shows every result vs the
    opponent, even when only one of the matches carries the note."""
    out: dict[dt.date, list[schemas.JournalMatchOut]] = {}
    for d, ms in _journal_day_match_rows(db, dates).items():
        for members in _group_day_matches(ms):
            group = _journal_group_out(members)
            if noted_only and not group.note:
                continue
            out.setdefault(d, []).append(group)
    return out


def set_match_note(db: Session, match_id: int, note: str) -> schemas.JournalMatchOut:
    """The journal's per-opponent-day note — writes tracker_match.note on the
    group's note-holder match (blank clears). Returns the GROUP so the
    composer's state stays aligned with what the day endpoint serves."""
    m = db.get(Match, match_id)
    if m is None:
        raise NotFound(f"match {match_id} not found")
    m.note = note.strip() or None
    db.commit()
    db.refresh(m)
    for members in _group_day_matches(
        _journal_day_match_rows(db, [m.date]).get(m.date, [])
    ):
        if any(x.id == m.id for x in members):
            return _journal_group_out(members)
    return _journal_group_out([m])  # unreachable: m is one of its day's matches


def _journal_day_out(
    db: Session, d: dt.date, items: list[SessionNote],
    coach_names: dict[str, list[str]] | None = None,
    matches: list[schemas.JournalMatchOut] | None = None,
) -> schemas.JournalDayOut:
    iso = d.isoformat()
    coaches = (
        coach_names.get(iso, [])
        if coach_names is not None
        else _journal_coach_names(db, [d]).get(iso, [])
    )
    return schemas.JournalDayOut(
        date=d,
        coaches=coaches,
        has_coach_session=has_coach_session(db, d),
        items=[session_note_to_out(n) for n in items],
        matches=matches or [],
    )


def journal_days(
    db: Session, limit: int = 30, before: dt.date | None = None
) -> schemas.JournalDaysOut:
    """The Journal timeline: days that HAVE entries (session notes OR noted
    matches), newest first, paginated by `before` (exclusive). Old Coach &
    Recap items appear as the journal of their day automatically — same
    store. Timeline days only carry the matches that HAVE notes."""
    sn_dates = {d for (d,) in db.query(SessionNote.date).distinct().all()}
    mn_dates = {
        d
        for (d,) in db.query(Match.date)
        .filter(
            Match.is_nonplaying == False,  # noqa: E712
            Match.note.isnot(None),
            Match.note != "",
        )
        .distinct()
        .all()
    }
    all_dates = sorted(sn_dates | mn_dates, reverse=True)
    if before is not None:
        all_dates = [d for d in all_dates if d < before]
    has_more = len(all_dates) > limit
    dates = all_dates[:limit]
    notes = (
        db.query(SessionNote)
        .filter(SessionNote.date.in_(dates))
        .order_by(SessionNote.id)
        .all()
    ) if dates else []
    by_date: dict[dt.date, list[SessionNote]] = {}
    for n in notes:
        by_date.setdefault(n.date, []).append(n)
    coach_names = _journal_coach_names(db, dates)
    match_by_date = _journal_matches(db, dates, noted_only=True)
    return schemas.JournalDaysOut(
        days=[
            _journal_day_out(
                db, d, by_date.get(d, []), coach_names, match_by_date.get(d, [])
            )
            for d in dates
        ],
        has_more=has_more,
    )


def journal_day(db: Session, d: dt.date) -> schemas.JournalDayOut:
    """One day for the Journal composer: items (may be empty), the
    has_coach_session gate flag, and ALL of the day's matches (note or not —
    the composer offers a note box per match)."""
    items = (
        db.query(SessionNote)
        .filter(SessionNote.date == d)
        .order_by(SessionNote.id)
        .all()
    )
    matches = _journal_matches(db, [d], noted_only=False).get(d, [])
    return _journal_day_out(db, d, items, matches=matches)
