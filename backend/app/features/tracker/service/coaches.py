"""Coaches and the 10-session coaching packages.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.core.errors import Conflict
from app.features.tracker import schemas
from app.features.tracker.models import (
    Activity,
    Category,
    Coach,
)

from .text import _fold

# Coaching packages: a block of N sessions; ★ marks the first session of a block.
COACH_PACKAGE_SIZE = 10


def coach_sessions_q(db: Session):
    """Query of every Train-with-Coach activity with real minutes — the one
    definition of "a coach session" (packages, journal, coach names). None
    when the category does not exist (fresh DB before the seed)."""
    coach = db.query(Category).filter(Category.key == "train_with_coach").first()
    if coach is None:
        return None
    return db.query(Activity).filter(
        Activity.category_id == coach.id, Activity.duration_minutes > 0
    )


def _coach_sessions(db: Session) -> list[Activity]:
    """Every coach session in date order — the single query behind all
    package computations. Includes second-coach sessions; package math
    filters them via _counts_toward_package."""
    q = coach_sessions_q(db)
    return [] if q is None else q.order_by(Activity.date).all()


def list_coaches(db: Session) -> list[Coach]:
    """All coaches, oldest first (the picker preselects the is_default one)."""
    return db.query(Coach).order_by(Coach.id).all()


def create_coach(db: Session, payload: schemas.CoachIn) -> Coach:
    """Add a coach from the session editor. Fold-compares the name so
    "phi vu" can't sit next to "Phi Vũ" (same dedupe rule as players)."""
    name = payload.name.strip()
    for c in db.query(Coach).all():
        if _fold(c.name) == _fold(name):
            raise Conflict(f'Coach "{c.name}" already exists.')
    c = Coach(name=name, counts_package=payload.counts_package)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def default_coach_id(db: Session) -> int | None:
    """The coach a new session gets when the caller names none: the row
    flagged is_default (Phi Vũ on the real DB since 2026-10-14), falling
    back to the oldest package coach when nothing is flagged."""
    row = (
        db.query(Coach.id)
        .filter(Coach.is_default.is_(True))
        .order_by(Coach.id)
        .first()
    ) or (
        db.query(Coach.id)
        .filter(Coach.counts_package.is_(True))
        .order_by(Coach.id)
        .first()
    )
    return row[0] if row else None


def _non_package_coach_ids(db: Session) -> set[int]:
    """Ids of pay-per-session coaches — their sessions never touch the block."""
    return {
        cid
        for (cid,) in db.query(Coach.id).filter(Coach.counts_package.is_(False))
    }


def _counts_toward_package(a: Activity, non_package_ids: set[int]) -> bool:
    """False for pay-per-session coaches' sessions; their is_package_start
    flag is ignored too — ★ on such a day is a no-op. coach_id None (legacy
    row the backfill missed) counts: the default coach is the package one."""
    return a.coach_id not in non_package_ids


def compute_coach_packages(db: Session) -> schemas.CoachPackagesResponse:
    """Group Train-with-Coach sessions into packages of COACH_PACKAGE_SIZE.

    A package opens on each session flagged is_package_start; the earliest
    session implicitly opens package #1 (covers data older than any marker).
    Pay-per-session coaches' sessions are skipped entirely; their per-coach
    counts since the current block opened are surfaced so a mis-assigned
    session stays visible on the card.
    """
    all_sessions = _coach_sessions(db)
    non_pkg_ids = _non_package_coach_ids(db)
    sessions = [a for a in all_sessions if _counts_toward_package(a, non_pkg_ids)]
    size = COACH_PACKAGE_SIZE
    packages: list[schemas.CoachPackage] = []
    for i, a in enumerate(sessions):
        opens = a.is_package_start or i == 0
        if opens:
            packages.append(
                schemas.CoachPackage(
                    number=len(packages) + 1,
                    start_date=a.date,
                    end_date=a.date,
                    used=1,
                    size=size,
                    remaining=max(0, size - 1),
                    over=0,
                    is_current=False,
                    status="ok",
                )
            )
        else:
            p = packages[-1]
            p.used += 1
            p.end_date = a.date
            p.remaining = max(0, size - p.used)
            p.over = max(0, p.used - size)

    # Status for every package (history included), not just the current one —
    # a past block that ran over should read "over" in the history list too.
    for p in packages:
        if p.over > 0:
            p.status = "over"
        elif p.remaining == 0:
            p.status = "done"
        elif p.remaining <= 2:
            p.status = "low"
        else:
            p.status = "ok"
    if packages:
        packages[-1].is_current = True

    # Pay-per-session counts since the current block opened (earlier ones are
    # history the card doesn't need to re-litigate). No block yet (every
    # session so far is per-session) → count them all: a mis-assigned first
    # session must still be visible on the card. Grouped per coach — most
    # sessions first, then name.
    floor = packages[-1].start_date if packages else None
    by_coach: dict[int | None, int] = {}
    for a in all_sessions:
        if _counts_toward_package(a, non_pkg_ids):
            continue
        if floor is not None and a.date < floor:
            continue
        by_coach[a.coach_id] = by_coach.get(a.coach_id, 0) + 1
    names = dict(db.query(Coach.id, Coach.name).all())
    non_package = [
        schemas.NonPackageCount(coach_name=names.get(cid, "?"), sessions=n)
        for cid, n in sorted(
            by_coach.items(), key=lambda kv: (-kv[1], names.get(kv[0], ""))
        )
    ]

    return schemas.CoachPackagesResponse(
        size=size, packages=packages, non_package=non_package
    )


def start_next_coach_package(db: Session) -> schemas.CoachPackagesResponse:
    """One-click card action: when the current block ran over its size, flag
    its (size+1)-th session as the next package's first session.

    Equivalent to opening that day's coach cell and ticking the ★ box — this
    just finds the right day automatically (always session 11, so sessions
    12+ stay in the NEW package, never inflate the old one)."""
    non_pkg_ids = _non_package_coach_ids(db)
    sessions = [
        a for a in _coach_sessions(db) if _counts_toward_package(a, non_pkg_ids)
    ]
    # Current block = everything from the last flagged start (or session #1).
    start_idx = 0
    for i, a in enumerate(sessions):
        if a.is_package_start:
            start_idx = i
    block = sessions[start_idx:]
    if len(block) <= COACH_PACKAGE_SIZE:
        raise Conflict(
            f"The current package only has {len(block)}/{COACH_PACKAGE_SIZE} "
            "sessions — no session has run over the package yet."
        )
    block[COACH_PACKAGE_SIZE].is_package_start = True
    db.commit()
    return compute_coach_packages(db)


def coach_package_start_allowed(db: Session, date: dt.date) -> bool:
    """Whether `date` may be marked as the start of a new coaching package.

    Allowed only when the day is the first session of its package (position 1 —
    so an existing start can be un-marked) or the 11th-or-later session of the
    current block (i.e. the previous 10 sessions are used up). Sessions 2..10
    of a block are NOT allowed. Works for a date that has no session yet
    (e.g. logging the 11th session for the first time).
    """
    all_sessions = _coach_sessions(db)
    non_pkg_ids = _non_package_coach_ids(db)
    # A pay-per-session coach's day can never open a package: compute ignores
    # its ★ entirely, so offering the checkbox would invite a silent no-op.
    own = [a for a in all_sessions if a.date == date]
    if own and not any(_counts_toward_package(a, non_pkg_ids) for a in own):
        return False
    sessions = [a for a in all_sessions if _counts_toward_package(a, non_pkg_ids)]
    if not sessions:
        return True  # the very first session can always open package #1

    # Package start dates = flagged sessions, plus an implicit first session.
    starts = sorted({s.date for s in sessions if s.is_package_start} | {sessions[0].date})

    applicable = [s for s in starts if s <= date]
    if not applicable:
        return True  # before the first start -> would become the new earliest start
    pkg_start = max(applicable)
    later = [s for s in starts if s > pkg_start]
    pkg_end = min(later) if later else None  # exclusive upper bound

    # Position of `date` within its block = (sessions in block before `date`) + 1.
    before = sum(
        1
        for s in sessions
        if s.date >= pkg_start
        and (pkg_end is None or s.date < pkg_end)
        and s.date < date
    )
    pos = before + 1
    return pos == 1 or pos >= COACH_PACKAGE_SIZE + 1
