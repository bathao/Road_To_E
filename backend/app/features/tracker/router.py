"""HTTP API for the Daily Tracker tab (prefix /api/tracker).

Thin by design: every handler maps HTTP to one service call; typed service
errors (app.core.errors) become the response codes."""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.features.tracker import schemas, service

router = APIRouter(prefix="/api/tracker", tags=["tracker"])


# ---------------------------------------------------------------- categories
@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return service.list_categories(db)


# ---------------------------------------------------------------- last date
@router.get("/last-date", response_model=schemas.LastDateResponse)
def last_date(db: Session = Depends(get_db)):
    """The most recent date that has any data (for opening the grid there)."""
    return schemas.LastDateResponse(date=service.latest_data_date(db))


@router.get("/first-date", response_model=schemas.LastDateResponse)
def first_date(db: Session = Depends(get_db)):
    """The earliest date that has any data (the Profile "Lifetime" range and
    the year/month lists of its range picker)."""
    return schemas.LastDateResponse(date=service.earliest_data_date(db))


# ---------------------------------------------------------------- week
@router.get("/weeks", response_model=schemas.WeekResponse)
def get_week(
    start: dt.date = Query(..., description="First day of the grid (YYYY-MM-DD)"),
    end: dt.date | None = Query(
        None, description="Last day of the grid; defaults to start+6 (a week)"
    ),
    db: Session = Depends(get_db),
):
    return service.build_week(db, start, end)


# --------------------------------------------------------- coach packages
@router.get("/coach-packages", response_model=schemas.CoachPackagesResponse)
def get_coach_packages(db: Session = Depends(get_db)):
    """Current + historical 10-session coaching packages (range-independent)."""
    return service.compute_coach_packages(db)


@router.post(
    "/coach-packages/start-next", response_model=schemas.CoachPackagesResponse
)
def start_next_coach_package(db: Session = Depends(get_db)):
    """Flag the over-run block's (size+1)-th session as the new package's start
    (the one-click button on the Coach Package card)."""
    return service.start_next_coach_package(db)


@router.get(
    "/coach-package-start-allowed",
    response_model=schemas.CoachStartAllowedResponse,
)
def coach_package_start_allowed(
    date: dt.date = Query(..., description="Day to test (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
):
    """Whether a given day may be marked as the start of a new coaching package."""
    return schemas.CoachStartAllowedResponse(
        allowed=service.coach_package_start_allowed(db, date)
    )


# ---------------------------------------------------------------- coaches
@router.get("/coaches", response_model=list[schemas.CoachOut])
def list_coaches(db: Session = Depends(get_db)):
    """All coaches, oldest first — feeds the session editor's picker."""
    return service.list_coaches(db)


@router.post("/coaches", response_model=schemas.CoachOut)
def create_coach(payload: schemas.CoachIn, db: Session = Depends(get_db)):
    return service.create_coach(db, payload)


# ---------------------------------------------------------------- activities
@router.put("/activities", response_model=schemas.ActivityOut | None)
def upsert_activity(payload: schemas.ActivityIn, db: Session = Depends(get_db)):
    """One call for the duration chips: upsert by (date, category). Empty -> delete."""
    return service.upsert_activity(db, payload)


# ---------------------------------------------------------------- matches
@router.post("/matches", response_model=schemas.MatchOut)
def create_match(payload: schemas.MatchIn, db: Session = Depends(get_db)):
    return service.create_match(db, payload)


@router.put("/matches/{match_id}", response_model=schemas.MatchOut)
def update_match(match_id: int, payload: schemas.MatchIn, db: Session = Depends(get_db)):
    return service.update_match(db, match_id, payload)


@router.delete("/matches/{match_id}", status_code=204)
def delete_match(match_id: int, db: Session = Depends(get_db)):
    service.delete_match(db, match_id)
    return Response(status_code=204)


@router.get(
    "/players/{player_id}/last-handicap",
    response_model=schemas.LastHandicapResponse,
)
def last_handicap(player_id: int, db: Session = Depends(get_db)):
    """Most recent singles handicap vs this opponent — the editor pre-fills
    the ratio when the opponent is picked (user can still change it)."""
    m = service.last_handicap_vs(db, player_id)
    if m is None:
        return schemas.LastHandicapResponse()
    return schemas.LastHandicapResponse(
        found=True, handicap=m.handicap or 0, handicap_pattern=m.handicap_pattern
    )


# ---------------------------------------------------------------- physical checklist
@router.get("/physical-items", response_model=list[schemas.PhysicalItemOut])
def list_physical_items():
    return [
        schemas.PhysicalItemOut(key=key, label=label)
        for key, label in service.PHYSICAL_ITEMS
    ]


@router.put("/physical-checks", response_model=schemas.PhysicalChecksOut)
def set_physical_checks(payload: schemas.PhysicalChecksIn, db: Session = Depends(get_db)):
    """Replace the full set of ticked items for a day."""
    return service.set_physical_checks(db, payload)


# ---------------------------------------------------------------- day notes
@router.put("/day-notes", response_model=schemas.DayNoteOut)
def upsert_day_note(payload: schemas.DayNoteIn, db: Session = Depends(get_db)):
    """Upsert a day's note. Empty text deletes it."""
    return service.upsert_day_note(db, payload)


# ------------------------------------------------- session notes (Journal tab)
@router.get("/journal/days", response_model=schemas.JournalDaysOut)
def journal_days(
    limit: int = Query(30, ge=1, le=120),
    before: dt.date | None = None,
    db: Session = Depends(get_db),
):
    """Journal timeline: days that have entries, newest first. `before`
    (exclusive) pages further back."""
    return service.journal_days(db, limit=limit, before=before)


@router.get("/journal/day/{date}", response_model=schemas.JournalDayOut)
def journal_day(date: dt.date, db: Session = Depends(get_db)):
    """One day for the composer — items, the coach-session gate flag and all
    of the day's matches (each with its note)."""
    return service.journal_day(db, date)


@router.patch("/matches/{match_id}/note", response_model=schemas.JournalMatchOut)
def set_match_note(
    match_id: int, payload: schemas.MatchNoteIn, db: Session = Depends(get_db)
):
    """The journal's per-match note (writes tracker_match.note; blank
    clears). The Tactics h2h context reads these notes."""
    return service.set_match_note(db, match_id, payload.note)


# ------------------------------------------------ tracking board (Journal tab)
@router.get("/tasks", response_model=schemas.TasksOut)
def list_tasks(db: Session = Depends(get_db)):
    """The Tracking board: open tasks + last week's done ones, with today's
    tick + streak on daily tasks. Every mutation below returns this list."""
    return service.list_tasks(db)


@router.post("/tasks", response_model=schemas.TasksOut)
def create_task(payload: schemas.TaskIn, db: Session = Depends(get_db)):
    return service.create_task(db, payload)


@router.patch("/tasks/{task_id}", response_model=schemas.TasksOut)
def update_task(
    task_id: int, payload: schemas.TaskUpdate, db: Session = Depends(get_db)
):
    return service.update_task(db, task_id, payload)


@router.delete("/tasks/{task_id}", response_model=schemas.TasksOut)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    return service.delete_task(db, task_id)


@router.post("/tasks/{task_id}/check", response_model=schemas.TasksOut)
def set_task_check(
    task_id: int, payload: schemas.TaskCheckIn, db: Session = Depends(get_db)
):
    """Tick / un-tick one day of a daily task (idempotent both ways)."""
    return service.set_task_check(db, task_id, payload)


# ------------------------------------------------ remember board (Journal tab)
@router.get("/memos", response_model=schemas.MemosOut)
def list_memos(db: Session = Depends(get_db)):
    """The Remember board: standing reminders in priority order. Every
    mutation below returns this list."""
    return service.list_memos(db)


@router.post("/memos", response_model=schemas.MemosOut)
def create_memo(payload: schemas.MemoIn, db: Session = Depends(get_db)):
    return service.create_memo(db, payload)


@router.patch("/memos/{memo_id}", response_model=schemas.MemosOut)
def update_memo(
    memo_id: int, payload: schemas.MemoUpdate, db: Session = Depends(get_db)
):
    return service.update_memo(db, memo_id, payload)


@router.delete("/memos/{memo_id}", response_model=schemas.MemosOut)
def delete_memo(memo_id: int, db: Session = Depends(get_db)):
    return service.delete_memo(db, memo_id)


@router.put("/memos/order", response_model=schemas.MemosOut)
def reorder_memos(payload: schemas.MemoReorderIn, db: Session = Depends(get_db)):
    """Set the priority order — the body lists EVERY current memo id."""
    return service.reorder_memos(db, payload)


@router.get("/session-note-tags", response_model=list[schemas.SessionNoteTagOut])
def list_session_note_tags():
    return [
        schemas.SessionNoteTagOut(key=key, label=label)
        for key, label in service.SESSION_NOTE_TAGS
    ]


@router.get("/session-notes/active", response_model=list[schemas.SessionNoteOut])
def list_active_advice(db: Session = Depends(get_db)):
    """All advice items not yet marked done, oldest first. No UI calls this
    since the checklist was dropped 2026-08-21 — kept for the AI bundle's
    "open advice" notion and pinned by tests."""
    return [service.session_note_to_out(n) for n in service.list_active_advice(db)]


@router.post("/session-notes", response_model=schemas.SessionNoteOut)
def create_session_note(payload: schemas.SessionNoteIn, db: Session = Depends(get_db)):
    n = service.create_session_note(db, payload)
    return service.session_note_to_out(n)


@router.patch("/session-notes/{note_id}", response_model=schemas.SessionNoteOut)
def update_session_note(
    note_id: int, payload: schemas.SessionNoteUpdate, db: Session = Depends(get_db)
):
    n = service.update_session_note(db, note_id, payload)
    return service.session_note_to_out(n)


@router.delete("/session-notes/{note_id}", status_code=204)
def delete_session_note(note_id: int, db: Session = Depends(get_db)):
    service.delete_session_note(db, note_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- events
@router.get("/events", response_model=list[schemas.EventOut])
def list_events(q: str = Query("", description="search term"), db: Session = Depends(get_db)):
    return service.list_events(db, q)


# ---------------------------------------------------------------- players
@router.get("/players", response_model=list[schemas.PlayerOut])
def list_players(q: str = Query("", description="search term"), db: Session = Depends(get_db)):
    """Opponent / partner pool, for the match-entry dropdown."""
    return service.list_players(db, q)


@router.post("/players", response_model=schemas.PlayerOut)
def create_player(payload: schemas.PlayerIn, db: Session = Depends(get_db)):
    """Add a new player (get-or-create by name); points optional, the legacy
    relative label is derived from them server-side."""
    return service.create_or_get_player(db, payload)


@router.put("/players/{player_id}", response_model=schemas.PlayerOut)
def update_player(player_id: int, payload: schemas.PlayerIn, db: Session = Depends(get_db)):
    updated = service.update_player(db, player_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return updated


# ---------------------------------------------------------------- database tab
@router.get("/players-db", response_model=schemas.PlayersDbResponse)
def players_db(db: Session = Depends(get_db)):
    """Every player + match count, rated first (the Database tab)."""
    return service.list_players_db(db)


@router.get("/players/{player_id}/matches", response_model=list[schemas.MatchOut])
def player_matches(player_id: int, db: Session = Depends(get_db)):
    """Every match involving this player (any slot) — the Database tab's
    per-player drill-down. All-time, newest first, ELO-annotated."""
    return service.list_player_matches(db, player_id)


@router.get("/my-rating", response_model=schemas.MyRatingOut)
def get_my_rating(db: Session = Depends(get_db)):
    """The user's rating — static anchor + replayed dynamic ELO (Phase 1a)."""
    return service.compute_my_rating(db)


@router.put("/my-rating", response_model=schemas.MyRatingOut)
def set_my_rating(payload: schemas.MyRatingIn, db: Session = Depends(get_db)):
    """Set a new anchor (today, points); the replay restarts from here."""
    service.set_my_points(db, payload.points)
    return service.compute_my_rating(db)


@router.get("/my-rating/breakdown", response_model=schemas.MyRatingBreakdownOut)
def my_rating_breakdown(
    date_from: dt.date = Query(..., alias="from"),
    date_to: dt.date = Query(..., alias="to"),
    unit: str = Query("day", pattern="^(day|week|month)$"),
    db: Session = Depends(get_db),
):
    """Net ELO change per bucket + every counted match's ±Δ. Global — no filters."""
    return service.build_rating_breakdown(db, date_from, date_to, unit)


# ---------------------------------------------------------------- stats
@router.get("/stats", response_model=schemas.StatsResponse)
def stats(
    date_from: dt.date = Query(..., alias="from"),
    date_to: dt.date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    return service.build_stats(db, date_from, date_to)


@router.get("/breakdown", response_model=schemas.BreakdownResponse)
def breakdown(
    date_from: dt.date = Query(..., alias="from"),
    date_to: dt.date = Query(..., alias="to"),
    unit: str = Query("month", pattern="^(month|week|day)$"),
    db: Session = Depends(get_db),
):
    return service.build_breakdown(db, date_from, date_to, unit)


@router.get("/match-stats", response_model=schemas.MatchStatsResponse)
def match_stats(
    date_from: dt.date = Query(..., alias="from"),
    date_to: dt.date = Query(..., alias="to"),
    discipline: str = Query("all", pattern="^(all|singles|doubles|one_v_two|two_v_one)$"),
    category: str = Query("all", pattern="^(all|practice|official|tournament)$"),
    unit: str = Query("month", pattern="^(month|week|day)$"),
    db: Session = Depends(get_db),
):
    """Match analytics over named-opponent matches only (the Profile tab).

    with_trend=False: the tab stopped rendering the trend buckets when its
    "Results & form" chart was removed (2026-08-01) — only the coach bundle
    (in-process) still reads them."""
    return service.build_match_stats(
        db, date_from, date_to, discipline, category, unit, with_trend=False
    )


# ---------------------------------------------------------------- export
@router.get("/export")
def export(
    date_from: dt.date = Query(..., alias="from"),
    date_to: dt.date = Query(..., alias="to"),
    format: str = Query("xlsx", pattern="^(xlsx|csv)$"),
    db: Session = Depends(get_db),
):
    stamp = f"{date_from.isoformat()}_{date_to.isoformat()}"
    if format == "csv":
        data = service.export_csv(db, date_from, date_to)
        media = "text/csv"
        filename = f"tracker_{stamp}.csv"
    else:
        data = service.export_xlsx(db, date_from, date_to)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"tracker_{stamp}.xlsx"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
