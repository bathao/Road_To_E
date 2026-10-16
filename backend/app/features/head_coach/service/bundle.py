"""Gather the coach's inputs: the verdict/chat bundle and the recap bundle (facts only).

Part of the head_coach service package (split 2026-10-16 from the former
1.6k-line service.py; see REFACTOR.md §4.2). Import names via
``app.features.head_coach.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.features.head_coach import schemas
from app.features.head_coach.models import (
    CoachNote,
)
from app.features.tournament import service as tournament_service
from app.features.tracker import rating as tracker_rating
from app.features.tracker import service as tracker_service
from app.features.tracker.models import DayNote, SessionNote
from app.features.training import service as training_service
from app.features.training.models import TrainingSession

from .common import _dm, _hdc_vi

# Window used for the volume / training-load stats fed to the coach.
_STATS_WINDOW_DAYS = 90


# Window for the detailed match analytics (head-to-head, level splits, trend).
# build_match_stats additionally clamps to its own data floor.
_MATCH_DETAIL_DAYS = 180


# How many recent day notes the coach reads (the player's own observations).
_RECENT_NOTES = 12


# Most-played singles head-to-heads fed to the verdict prompt.
_VERDICT_H2H = 8


# Per-opponent progression: recent matches (oldest → newest) per h2h line, so
# the model can compare new vs old results at the SAME handicap ratio.
_H2H_PROGRESSION = 6


# Biggest per-opponent ELO drains/sources (each side) fed to the prompts.
_ELO_OPP_TOP = 4


# ---------------------------------------------------------------- gather inputs
def _ms(m) -> dict:
    return {"played": m.total, "wins": m.wins, "losses": m.losses, "win_rate": m.win_rate}


def _h2h_progression(lines, limit: int = _H2H_PROGRESSION) -> str:
    """"05/07 L 0-3 (được chấp 2) → 03/08 L 2-3 (được chấp 2)" — one
    opponent's recent matches oldest → newest (W/L/T like the rest of the
    context), each with its handicap, so the model can compare new vs old
    results at the same ratio. OpponentRecord.matches arrives most-recent
    FIRST (the GUI's order) — take the newest `limit`, then flip."""
    return " → ".join(
        f"{_dm(ml.date.isoformat())} {ml.result} {ml.my_sets}-{ml.opp_sets} "
        f"({_hdc_vi(ml.handicap, ml.handicap_pattern)})"
        for ml in reversed(lines[:limit])
    )


def _elo_opp_split(rows: list[dict]) -> dict:
    """Top ELO sources (net > 0) and drains (net < 0), biggest first.
    `rows` comes from tracker_service.elo_by_opponent (sorted net desc)."""
    return {
        "gains": [r for r in rows if r["net"] > 0][:_ELO_OPP_TOP],
        "drains": [r for r in reversed(rows) if r["net"] < 0][:_ELO_OPP_TOP],
    }


def _task_dicts(db: Session, today: dt.date) -> list[dict]:
    """The Tracking board's OPEN tasks as prompt-ready dicts. Daily tasks
    carry streak / days-since-last, so the coach praises or nudges from
    real numbers instead of guessing."""
    src_vi = {"coach": "HLV giao", "ai": "AI đề xuất", "self": "tự giao"}
    status_vi = {"todo": "chưa bắt đầu", "doing": "đang làm"}
    out: list[dict] = []
    for t in tracker_service.list_tasks(db, today).tasks:
        if t.status == "done":
            continue
        d: dict = {
            "title": t.title,
            "source": src_vi.get(t.source, t.source),
            "status": status_vi.get(t.status, t.status),
        }
        if t.note:
            d["note"] = t.note
        if t.is_daily:
            d["daily"] = True
            d["streak"] = t.streak
            d["days_since_last"] = (
                (today - t.last_check).days if t.last_check else None
            )
        out.append(d)
    return out


def _memo_dicts(db: Session) -> list[dict]:
    """The Remember board as prompt-ready dicts, priority order — what the
    player has pinned to re-read every day (self-set rules; the coach can
    check whether the numbers show them being followed)."""
    return [{"text": m.text} for m in tracker_service.list_memos(db).memos]


def _session_note_dict(n: SessionNote, with_kind: bool = False) -> dict:
    """One journal session-note item as a prompt-ready dict (tag keys →
    display labels). Shared by the verdict bundle and the recap bundle."""
    tags = [t for t in (n.tags or "").split(",") if t]
    out = {
        "date": n.date.isoformat(),
        "text": n.text,
        "tags": [tracker_service.SESSION_NOTE_TAG_LABELS.get(t, t) for t in tags],
    }
    if with_kind:
        out["kind"] = n.kind
    return out


def coach_note_dicts(db: Session) -> list[dict]:
    """The coach's notebook as prompt dicts — oldest first, so later notes
    read as refinements. Shared by the verdict and recap bundles."""
    return [
        {"date": n.created_at.date().isoformat() if n.created_at else "", "text": n.text}
        for n in db.query(CoachNote).order_by(CoachNote.created_at.asc()).all()
    ]


def _player_name(db: Session) -> str:
    """The player's name, read straight from the retired profile table.

    The video_analysis feature was deleted (2026-07-29) but its va_profile row
    is user data and stays in SQLite; this is the one field the coach needs.
    """
    try:
        row = db.execute(text("SELECT name FROM va_profile WHERE id = 1")).first()
        return row[0] if row and row[0] else "the player"
    except Exception:
        return "the player"


def _training_summary(training) -> dict:
    """The Training Center facts the coach reads (physical load/adherence)."""
    return {
        "level": training.current_level_vi,
        "total_sessions_done": training.total_sessions_done,
        "sessions_last_7d": training.sessions_last_7d,
        "sessions_last_30d": training.sessions_last_30d,
        "days_since_last": training.days_since_last,
        "current_streak": training.current_streak,
        "intensity_bias": training.intensity_bias,
        "muscle_volume": {mv.muscle: mv.times for mv in training.muscle_volume},
        # NOTE: summary_vi (English GUI prose) is deliberately NOT fed to the
        # coach — its Vietnamese prompt gets the raw numbers above instead.
    }


def _match_summary(
    db: Session, today: dt.date, rep: "tracker_rating.ReplayResult"
) -> dict:
    """Volume + per-discipline results over the stats window, plus the
    dynamic ELO (the coach's objective progress yardstick) and its weekly
    trend — the DIRECTION matters more than any single number."""
    date_from = today - dt.timedelta(days=_STATS_WINDOW_DAYS)
    stats = tracker_service.build_stats(db, date_from, today)
    out = {
        "window_days": _STATS_WINDOW_DAYS,
        "days_trained": stats.days_trained,
        "days_physical": stats.days_physical,
        "minutes_total": stats.minutes_total,
        "minutes_by_category": {c.label: c.minutes for c in stats.minutes_by_category},
        "racket_minutes_total": stats.racket_minutes_total,
        "racket_minutes_training": stats.racket_minutes_training,
        "racket_minutes_matches": stats.racket_minutes_matches,
        "overall": _ms(stats.overall),
        "singles": _ms(stats.singles),
        "doubles": _ms(stats.doubles),
        "one_v_two": _ms(stats.one_v_two),
        "two_v_one": _ms(stats.two_v_one),
        "vs_pips": _ms(stats.vs_pips),
    }
    my_elo = tracker_service.compute_my_rating(db, replay_result=rep)
    # with_movers=False: the bundle reads only the weekly buckets — no need
    # to build a per-match row for every counted match.
    elo_trend = tracker_service.build_rating_breakdown(
        db, today - dt.timedelta(days=41), today, unit="week", replay=rep,
        with_movers=False,
    )
    out["my_elo"] = {
        "current": my_elo.current,
        "anchor": my_elo.points,
        "anchor_date": my_elo.anchor_date,
        "counted_matches": my_elo.counted_matches,
        "to_rank_e": max(0, tracker_rating.RANK_E_FLOOR - my_elo.current),
        "weekly": [
            {
                "from": b.date_from.isoformat(),
                "to": b.date_to.isoformat(),
                "delta": b.delta,
                "counted": b.counted,
                "rating_end": b.rating_end,
            }
            for b in elo_trend.buckets
            if b.rating_end is not None  # weeks fully before the anchor: no rating
        ],
    }
    return out


def _match_detail(
    db: Session, today: dt.date, rep: "tracker_rating.ReplayResult"
) -> dict:
    """Named-opponent analytics: level × handicap splits, per-kind results,
    monthly trend and the most-played singles head-to-heads (problem
    opponents float up via win_rate)."""
    detail_from = today - dt.timedelta(days=_MATCH_DETAIL_DAYS)
    # The three per-kind calls read `.overall` only → overall_only skips
    # their h2h/new-opponents/trend work entirely.
    def _stats(category: str, overall_only: bool = False):
        return tracker_service.build_match_stats(
            db, detail_from, today, "all", category, "month",
            replay=rep, overall_only=overall_only,
        )

    detail = _stats("all")
    practice = _stats("practice", overall_only=True)
    official = _stats("official", overall_only=True)
    tournament = _stats("tournament", overall_only=True)
    top_h2h = sorted(detail.singles_h2h, key=lambda r: -r.played)[:_VERDICT_H2H]
    return {
        "window": f"{detail.date_from.isoformat()} → {detail.date_to.isoformat()}",
        # Level × handicap direction (even / receiving / giving points): a
        # handicapped match must be read differently from an even one.
        # (The plain by-level split was dropped 2026-07-29 with its GUI —
        # this table still carries per-level context, ELO covers the rest.)
        "by_level_handicap": tracker_service.build_handicap_split(
            db, detail_from, today, replay=rep
        ),
        # Kinds: practice = đánh chơi, official = đánh độ nhẹ, tournament =
        # đánh giải (new 2026-07-26 — zero rows until the user logs one).
        "practice": _ms(practice.overall),
        "official": _ms(official.overall),
        "tournament": _ms(tournament.overall),
        "trend_by_month": [
            {
                "label": b.label,
                "played": b.matches,
                "wins": b.wins,
                "losses": b.losses,
                "win_rate": b.win_rate,
            }
            for b in detail.trend
        ],
        "top_h2h": [
            {
                "name": r.name,
                "level": r.level,
                "played": r.played,
                "wins": r.wins,
                "losses": r.losses,
                "win_rate": r.win_rate,
                "last": f"{r.last_result or ''} {r.last_date.isoformat() if r.last_date else ''}".strip(),
                # Oldest → newest, each with its handicap — the prompt's
                # progression rule compares results at the SAME ratio.
                "recent": _h2h_progression(r.matches),
            }
            for r in top_h2h
        ],
        # Who the ELO is being lost to / won from over the same window —
        # the prompt turns this into kèo-selection strategy.
        "elo_by_opponent": _elo_opp_split(
            tracker_service.elo_by_opponent(db, detail_from, today, replay=rep)
        ),
    }


def gather_bundle(db: Session) -> schemas.SourceSummary:
    """Assemble the coach's inputs — hard facts from the database ONLY.

    Sources: the Daily Tracker (per-day volume + every match with its score,
    opponent level, pips, practice/official) and the Training Center (physical
    load, adherence, pain). No AI-derived skill ratings: the retired technique-
    analysis pipeline produced model guesses, not observations."""
    today = dt.date.today()

    # ONE ELO replay shared by every rating-dependent build below — the bundle
    # runs on every verdict AND every chat message, and a replay walks every
    # match since the anchor.
    rep = tracker_rating.replay(db)

    training_sum = _training_summary(training_service.report(db))
    match_sum = _match_summary(db, today, rep)
    match_detail = _match_detail(db, today, rep)

    # The player's own day notes — human observations, newest first.
    notes = [
        {"date": n.date.isoformat(), "text": n.text}
        for n in db.query(DayNote).order_by(DayNote.date.desc()).limit(_RECENT_NOTES).all()
    ]

    # What the REAL-LIFE coach is asking for (all still-active advice, oldest
    # first) + what recent coach sessions covered (recaps, newest first).
    coach_advice = [
        _session_note_dict(n) for n in tracker_service.list_active_advice(db)
    ]
    # Drills count as recap material (what was actually practiced) — prefixed
    # so the model can tell one exercise from an overall summary. Lessons are
    # NOT recap material — they get their own section below.
    session_recaps = [
        _session_note_dict(n)
        | (
            {"text": f"Bài tập: {n.text}"}
            if n.kind == tracker_service.SN_KIND_DRILL
            else {}
        )
        for n in db.query(SessionNote)
        .filter(SessionNote.kind.in_(
            (tracker_service.SN_KIND_DRILL, tracker_service.SN_KIND_RECAP)
        ))
        .order_by(SessionNote.date.desc(), SessionNote.id.desc())
        .limit(_RECENT_NOTES)
        .all()
    ]

    # The player's own takeaways from the Journal tab (2026-08-20), newest
    # first — self-observed, cross-checkable against the numbers.
    lessons = [
        _session_note_dict(n)
        for n in db.query(SessionNote)
        .filter(SessionNote.kind == tracker_service.SN_KIND_LESSON)
        .order_by(SessionNote.date.desc(), SessionNote.id.desc())
        .limit(_RECENT_NOTES)
        .all()
    ]

    return schemas.SourceSummary(
        tasks=_task_dicts(db, today),
        memos=_memo_dicts(db),
        player=_player_name(db),
        training=training_sum,
        match=match_sum,
        match_detail=match_detail,
        notes=notes,
        coach_advice=coach_advice,
        session_recaps=session_recaps,
        lessons=lessons,
        coach_notes=coach_note_dicts(db),
        # Registered upcoming competitions — the week plan aims at these.
        tournaments=tournament_service.upcoming_for_coach(db),
        generated_for_range=(
            f"{(today - dt.timedelta(days=_STATS_WINDOW_DAYS)).isoformat()}"
            f" → {today.isoformat()}"
        ),
    )


# ------------------------------------------------------- weekly/monthly recap
# The recap looks back over a ROLLING window ending TODAY — week = the last
# 7 days, month = the last 30 days, results up to the moment the button is
# pressed (redesigned 2026-08-01; the original closed-calendar-period +
# lazy-auto-generate version was cut on first contact — the user wants an
# explicit button, exactly like the verdict's Re-analyze).
_RECAP_PERIODS = ("week", "month")


_RECAP_WINDOW_DAYS = {"week": 7, "month": 30}


# Most-played in-period head-to-heads fed to the recap prompt.
_RECAP_H2H = 5


def _period_label_vi(period_type: str, start: dt.date, end: dt.date) -> str:
    # period_type is validated against _RECAP_PERIODS before any row exists.
    days = _RECAP_WINDOW_DAYS[period_type]
    return f"{days} NGÀY GẦN NHẤT ({start.isoformat()} → {end.isoformat()})"


def _period_stats(
    db: Session, start: dt.date, end: dt.date, rep: "tracker_rating.ReplayResult"
) -> tuple:
    """Code-computed snapshot for one period (+ the full StatsResponse and
    the ELO breakdown, so the bundle can reuse both without querying twice)."""
    stats = tracker_service.build_stats(db, start, end)
    elo = tracker_service.build_rating_breakdown(
        db, start, end, unit="week", replay=rep, with_movers=False
    )
    physical_sessions = (
        db.query(TrainingSession)
        .filter(
            TrainingSession.status == "done",
            TrainingSession.done_on >= start,
            TrainingSession.done_on <= end,
        )
        .count()
    )
    snapshot = schemas.RecapPeriodStats(
        days_trained=stats.days_trained,
        days_physical=stats.days_physical,
        minutes_total=stats.minutes_total,
        racket_minutes_total=stats.racket_minutes_total,
        matches_played=stats.overall.total,
        matches_wins=stats.overall.wins,
        matches_losses=stats.overall.losses,
        win_rate=stats.overall.win_rate,
        elo_delta=elo.total_delta,
        elo_end=elo.rating_end,
        elo_counted=elo.counted,
        physical_sessions=physical_sessions,
        new_opponents=tracker_service.count_new_opponents(db, start, end),
    )
    return snapshot, stats, elo


def gather_recap_bundle(
    db: Session,
    period_type: str,
    start: dt.date,
    end: dt.date,
    rep: "tracker_rating.ReplayResult",
    stats: schemas.RecapStats,
    full_stats,
    elo,
) -> dict:
    """The recap's inputs: the code-computed snapshot pair + in-period detail
    (per-discipline/kind results, ELO buckets, h2h, notes, coach sessions).
    `full_stats` / `elo` come from _period_stats — no recomputation here."""
    detail = tracker_service.build_match_stats(
        db, start, end, "all", "all", "week", replay=rep
    )

    def _kind(category: str) -> dict:
        # `.overall` only → overall_only skips the h2h/new-opponents work.
        return _ms(
            tracker_service.build_match_stats(
                db, start, end, "all", category, "week",
                replay=rep, overall_only=True,
            ).overall
        )

    top_h2h = sorted(detail.singles_h2h, key=lambda r: -r.played)[:_RECAP_H2H]

    session_notes = [
        _session_note_dict(n, with_kind=True)
        for n in db.query(SessionNote)
        .filter(SessionNote.date >= start, SessionNote.date <= end)
        .order_by(SessionNote.date.asc(), SessionNote.id.asc())
        .all()
    ]
    day_notes = [
        {"date": n.date.isoformat(), "text": n.text}
        for n in db.query(DayNote)
        .filter(DayNote.date >= start, DayNote.date <= end)
        .order_by(DayNote.date.asc())
        .all()
    ]

    return {
        "player": _player_name(db),
        "period_type": period_type,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "stats": stats.model_dump(mode="json"),
        "results": {
            "singles": _ms(full_stats.singles),
            "doubles": _ms(full_stats.doubles),
            "one_v_two": _ms(full_stats.one_v_two),
            "two_v_one": _ms(full_stats.two_v_one),
            "vs_pips": _ms(full_stats.vs_pips),
            "overall": _ms(full_stats.overall),
        },
        "by_kind": {
            "practice": _kind("practice"),
            "official": _kind("official"),
            "tournament": _kind("tournament"),
        },
        "minutes_by_category": {
            c.label: c.minutes for c in full_stats.minutes_by_category
        },
        "elo_weekly": [
            {
                "from": b.date_from.isoformat(),
                "to": b.date_to.isoformat(),
                "delta": b.delta,
                "counted": b.counted,
                "rating_end": b.rating_end,
            }
            for b in elo.buckets
            if b.rating_end is not None
        ],
        "top_h2h": [
            {
                "name": r.name,
                "level": r.level,
                "played": r.played,
                "wins": r.wins,
                "losses": r.losses,
                # In-period matches oldest → newest with handicap — the
                # progression rule compares results at the SAME ratio.
                "recent": _h2h_progression(r.matches),
            }
            for r in top_h2h
        ],
        # Who the period's ELO went to / came from (kèo-selection input).
        "elo_by_opponent": _elo_opp_split(
            tracker_service.elo_by_opponent(db, start, end, replay=rep)
        ),
        "session_notes": session_notes,
        "day_notes": day_notes,
        "coach_notes": coach_note_dicts(db),
        # Open Tracking-board tasks as of the period's end — the recap can
        # note kept/broken daily streaks alongside the period's numbers.
        "tasks": _task_dicts(db, end),
        # The Remember board as it stands now (no history — standing rules).
        "memos": _memo_dicts(db),
    }
