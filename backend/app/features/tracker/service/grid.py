"""The Daily Tracker grid: range loading, cell rendering, Overall colours, week build.

Part of the tracker service package (split 2026-10-16 from the former
2.7k-line service.py; see REFACTOR.md §3.1). Import names via
``app.features.tracker.service`` — the package __init__ re-exports them.
"""
from __future__ import annotations

import datetime as dt
from typing import NamedTuple

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.features.tracker import schemas
from app.features.tracker.constants import DISCIPLINE_PREFIX, DISCIPLINES, ROUND_SHORT
from app.features.tracker.models import (
    Activity,
    Category,
    Coach,
    DayNote,
    Match,
    PhysicalCheck,
)
from app.features.training import service as training_service

from .matches import _annotate_elo
from .periods import _date_range
from .tally import _result_letter
from .text import _fold

# Fixed checklist for the Physical Training row. (key, English label)
PHYSICAL_ITEMS: list[tuple[str, str]] = [
    ("wall_sit", "Wall Sit"),
    ("sit_ups", "Sit-ups"),
    ("plank", "Plank"),
    ("squats", "Squats"),
    ("obliques", "Obliques"),
    ("stretching", "Stretching"),
]


PHYSICAL_ITEM_LABELS = dict(PHYSICAL_ITEMS)


def physical_checks_by_date(checks: list[PhysicalCheck]) -> dict[str, list[str]]:
    """Group ticked item keys per ISO date, in the canonical item order."""
    order = {key: i for i, (key, _) in enumerate(PHYSICAL_ITEMS)}
    grouped: dict[str, list[str]] = {}
    for c in checks:
        grouped.setdefault(c.date.isoformat(), []).append(c.item_key)
    for iso in grouped:
        grouped[iso].sort(key=lambda k: order.get(k, 999))
    return grouped


def format_physical_cell(item_keys: list[str]) -> str:
    """Render ticked items as their labels, separated by a middot divider."""
    return " · ".join(PHYSICAL_ITEM_LABELS.get(k, k) for k in item_keys)


def physical_is_yellow(item_keys: list[str]) -> bool:
    """Yellow once at least the Training Center's share of items is ticked —
    the ratio's single source of truth lives there (same rule for its own
    sessions)."""
    if not PHYSICAL_ITEMS:
        return False
    return len(item_keys) / len(PHYSICAL_ITEMS) >= training_service.PHYSICAL_YELLOW_RATIO


# Max characters shown for a note in the (compact) grid cell.
_NOTE_SNIPPET_LEN = 22


PACKAGE_MARK = "★"


# ------------------------------------------------------------- racket time
# "Racket Time" = total time with the racket in hand per day: the coach +
# partner training minutes plus the match play estimated from set counts
# (a set averages ~5 minutes). Serve practice / physical work don't count.
RACKET_MINUTES_PER_SET = 5


RACKET_DURATION_KEYS = ("train_with_coach", "training_with_partner")


def racket_minutes_by_day(
    categories: list["Category"],
    activities: list["Activity"],
    matches: list["Match"],
) -> tuple[dict[str, int], dict[str, int]]:
    """Per ISO day: (training minutes from coach+partner, match minutes from
    sets × RACKET_MINUTES_PER_SET). Non-playing entries (Travel/Rest) don't
    count. Racket time for a day = the sum of the two maps' values."""
    racket_ids = {c.id for c in categories if c.key in RACKET_DURATION_KEYS}
    training: dict[str, int] = {}
    playing: dict[str, int] = {}
    for a in activities:
        if a.category_id in racket_ids and (a.duration_minutes or 0) > 0:
            iso = a.date.isoformat()
            training[iso] = training.get(iso, 0) + a.duration_minutes
    for m in matches:
        if m.is_nonplaying:
            continue
        sets = (m.my_sets or 0) + (m.opp_sets or 0)
        if sets <= 0:
            continue
        iso = m.date.isoformat()
        playing[iso] = playing.get(iso, 0) + sets * RACKET_MINUTES_PER_SET
    return training, playing


def note_snippet(text: str) -> str:
    """A compact one-line preview for the grid cell ('📝 ...'). Full text lives
    in the editor / export."""
    s = " ".join((text or "").split())
    if len(s) > _NOTE_SNIPPET_LEN:
        s = s[:_NOTE_SNIPPET_LEN].rstrip() + "…"
    return f"📝 {s}".rstrip()


def format_duration(minutes: int) -> str:
    """60 -> '1 hour', 45 -> '45 mins', 90 -> '1 hour 30 mins'."""
    if not minutes:
        return ""
    hours, mins = divmod(minutes, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours} hour")
    if mins:
        parts.append(f"{mins} mins")
    return " ".join(parts)


# Fixed ordering of result groups within a cell.
_GROUP_ORDER = [(d, r) for d in DISCIPLINES for r in ("W", "L", "T")]


def _match_result_lines(playing: list[Match]) -> list[str]:
    """The W/L score lines for one batch of playing matches (already in play
    order). Group-stage/no-round scores group by (discipline, result) —
    'W(3-0,3-1)' / 'D: L(1-3)'; knockout-round matches (QF/SF/…) get their
    own line per round instead — 'QF: W(3-1)' reads like the bracket."""
    groups: dict[tuple[str, str], list[str]] = {}
    knockout: list[str] = []
    for m in playing:
        result = _result_letter(m.my_sets, m.opp_sets)
        round_label = ROUND_SHORT.get(m.round or "group", "")
        if round_label:
            prefix = DISCIPLINE_PREFIX.get(m.discipline, "")
            knockout.append(
                f"{round_label}: {prefix}{result}({m.my_sets}-{m.opp_sets})"
            )
            continue
        key = (m.discipline, result)
        groups.setdefault(key, []).append(f"{m.my_sets}-{m.opp_sets}")

    lines: list[str] = []
    ordered_keys = _GROUP_ORDER + [k for k in groups if k not in _GROUP_ORDER]
    for key in ordered_keys:
        scores = groups.get(key)
        if not scores:
            continue
        discipline, result = key
        prefix = DISCIPLINE_PREFIX.get(discipline, "")
        lines.append(f"{prefix}{result}({','.join(scores)})")
    lines.extend(knockout)  # in play order, after the grouped results
    return lines


def format_match_cell(matches: list[Match]) -> str:
    """Render a day's matches the way the Excel sheet shows them.

    Single (or no) event: non-playing labels + the event name on their own
    lines, then the grouped scores. MULTIPLE events on one day (a
    several-tier tournament weekend — user 2026-08-23): the scores nest
    UNDER their event name so each tournament reads separately, with
    event-less matches last.
    """
    if not matches:
        return ""

    ordered = sorted(matches, key=lambda m: m.order_index)
    lines: list[str] = []

    # Non-playing markers (Travel / Rest).
    for m in ordered:
        if m.is_nonplaying and m.nonplaying_label and m.nonplaying_label not in lines:
            lines.append(m.nonplaying_label)

    playing = [m for m in ordered if not m.is_nonplaying]
    # Event names (distinct, first-seen order).
    events: list[str] = []
    for m in playing:
        if m.event and m.event.name and m.event.name not in events:
            events.append(m.event.name)

    if len(events) > 1:
        for ev in events:
            lines.append(ev)
            lines.extend(
                _match_result_lines(
                    [m for m in playing if m.event and m.event.name == ev]
                )
            )
        loose = [m for m in playing if not (m.event and m.event.name)]
        lines.extend(_match_result_lines(loose))
    else:
        lines.extend(events)
        lines.extend(_match_result_lines(playing))

    return "\n".join(lines)


def earliest_data_date(db: Session) -> dt.date | None:
    """The first day that has any tracked data (for the red 'rest-day' bound)."""
    tc_lo, _ = training_service.done_date_bounds(db)
    candidates = [
        db.query(func.min(Activity.date)).scalar(),
        db.query(func.min(Match.date)).scalar(),
        db.query(func.min(PhysicalCheck.date)).scalar(),
        tc_lo,
    ]
    dates = [d for d in candidates if d is not None]
    return min(dates) if dates else None


def has_data_between(db: Session, date_from: dt.date, date_to: dt.date) -> bool:
    """Whether ANY tracked data exists inside the range — the same four
    sources as earliest_data_date (activities, matches, legacy physical
    checks, Training Center sessions). Used e.g. to refuse generating a
    coach recap over an empty window."""
    for model, col in (
        (Activity, Activity.date),
        (Match, Match.date),
        (PhysicalCheck, PhysicalCheck.date),
    ):
        if db.query(model.id).filter(col >= date_from, col <= date_to).first() is not None:
            return True
    from app.features.training.models import TrainingSession  # local: no cycle

    return (
        db.query(TrainingSession.id)
        .filter(
            TrainingSession.status == "done",
            TrainingSession.done_on >= date_from,
            TrainingSession.done_on <= date_to,
        )
        .first()
        is not None
    )


def latest_data_date(db: Session) -> dt.date | None:
    """The most recent day that has any tracked data (for opening the grid there)."""
    _, tc_hi = training_service.done_date_bounds(db)
    candidates = [
        db.query(func.max(Activity.date)).scalar(),
        db.query(func.max(Match.date)).scalar(),
        db.query(func.max(PhysicalCheck.date)).scalar(),
        tc_hi,
    ]
    dates = [d for d in candidates if d is not None]
    return max(dates) if dates else None


# Overall row's green bar: a real racket-time day (user rule 2026-08-04:
# "xanh = đang đi đúng hướng tới E"). >= so a standard 1h coach session stays
# green; 60p of match play = 12 sets ≈ 4 BO5 matches.
OVERALL_GREEN_RACKET_MINUTES = 60


def compute_overall_colors(
    categories: list[Category],
    activities: list[Activity],
    matches: list[Match],
    physical_dates: set[str] | None = None,
    all_days: list[dt.date] | None = None,
    today: dt.date | None = None,
    earliest: dt.date | None = None,
    racket: tuple[dict[str, int], dict[str, int]] | None = None,
) -> dict[str, str]:
    """Auto-generate the 'Overall' color per day (no manual rating).

    User rule 2026-08-04 — the grid measures QUANTITY, quality is ELO's job:
    - green: total racket time that day >= 60 minutes (coach + partner
      training plus match play from sets × 5p — the same number as the
      Racket Time row). The old rule (green = any minutes on a green-group
      row) was volume-blind: 15p of drills was green while a 5-match
      sparring evening could never be — backwards for the road-to-E goal.
    - yellow: something logged but under the bar — a short racket day, a
      physical day, any other duration row (serve practice is deliberate
      but not racket time), or any match row (a legacy Travel/Rest entry is
      data, not "nothing").
    - red: a past day (>= the first tracked day, < today) with no data at all.
    - (absent): no data, and the day is today, in the future, or before tracking
      began.

    Returns {iso_date: 'green' | 'yellow' | 'red'}.
    """
    # `racket` = precomputed racket_minutes_by_day maps — the grid renderer
    # already builds them for the Racket Time row, so it passes them in.
    r_train, r_play = racket or racket_minutes_by_day(categories, activities, matches)

    green_days: set[str] = set()
    other_days: set[str] = set(physical_dates or set())

    for iso in set(r_train) | set(r_play):
        total = r_train.get(iso, 0) + r_play.get(iso, 0)
        if total >= OVERALL_GREEN_RACKET_MINUTES:
            green_days.add(iso)
        else:
            other_days.add(iso)

    # Anything else logged still marks the day as "not nothing".
    for a in activities:
        if (a.duration_minutes or 0) > 0:
            other_days.add(a.date.isoformat())
    for m in matches:
        other_days.add(m.date.isoformat())

    colors: dict[str, str] = {}
    for iso in green_days | other_days:
        colors[iso] = "green" if iso in green_days else "yellow"

    # Empty past days within the tracked range -> red ("didn't train").
    if all_days and today:
        for d in all_days:
            iso = d.isoformat()
            if iso in colors:
                continue
            if earliest is not None and earliest <= d < today:
                colors[iso] = "red"
    return colors


class RangeData(NamedTuple):
    categories: list[Category]
    activities: list[Activity]
    matches: list[Match]  # ordered by order_index
    checks_by_date: dict[str, list[str]]  # iso date -> ticked item keys (legacy)
    notes_by_date: dict[str, str]  # iso date -> day-note text
    # Training Center sessions completed in-range, keyed by done date. From the
    # cutover forward these are the source of the physical-training signal.
    tc_physical: dict[str, dict]


def _load_range(
    db: Session,
    date_from: dt.date,
    date_to: dt.date,
    with_match_relations: bool = True,
) -> RangeData:
    """Load the four range-filtered tables shared by the week / stats /
    breakdown / export builders, so each one stops re-issuing the same queries.

    ``with_match_relations`` eager-loads each match's event/opponent/partner via
    selectinload (avoids N+1 where they're rendered); callers that only count
    matches (stats / breakdown) pass False to skip the extra queries.
    """
    # session_note-type categories are OUT of the grid since 2026-08-20: the
    # Coach & Recap row moved to the Journal tab (same store, new surface).
    categories = (
        db.query(Category)
        .filter(Category.type != "session_note")
        .order_by(Category.sort_order)
        .all()
    )
    activities = (
        db.query(Activity)
        .filter(Activity.date >= date_from, Activity.date <= date_to)
        .all()
    )
    match_q = db.query(Match).filter(Match.date >= date_from, Match.date <= date_to)
    if with_match_relations:
        match_q = match_q.options(
            selectinload(Match.event),
            selectinload(Match.opponent),
            selectinload(Match.opponent2),
            selectinload(Match.partner),
        )
    matches = match_q.order_by(Match.order_index).all()
    checks = (
        db.query(PhysicalCheck)
        .filter(PhysicalCheck.date >= date_from, PhysicalCheck.date <= date_to)
        .all()
    )
    day_notes = (
        db.query(DayNote)
        .filter(DayNote.date >= date_from, DayNote.date <= date_to)
        .all()
    )
    return RangeData(
        categories=categories,
        activities=activities,
        matches=matches,
        checks_by_date=physical_checks_by_date(checks),
        notes_by_date={n.date.isoformat(): n.text for n in day_notes},
        tc_physical=training_service.physical_day_map(db, date_from, date_to),
    )


def _physical_dates(rng: RangeData) -> set[str]:
    """All dates that count as a physical-training day: legacy checklist ticks
    (before the cutover) unioned with completed Training Center sessions (from
    the cutover forward). The two never overlap, so this can't double-count."""
    return set(rng.checks_by_date.keys()) | set(rng.tc_physical.keys())


def _grid_cells(
    db: Session, rng: RangeData, days: list[dt.date], *, for_export: bool
) -> tuple[dict[tuple[int, str], str], dict[tuple[int, str], str], dict[str, str]]:
    """The ONE cell renderer behind both the on-screen grid (build_week) and
    the export (_build_grid). They used to be two ~70-line near-copies that
    drifted (the export-parity bug came from exactly that), so every row type
    renders here exactly once.

    Returns (text, colors, overall_color_by_date); text/colors are keyed by
    (category_id, iso date). ``for_export``: day notes render in full (the
    screen shows the compact 📝 snippet; full text travels in day_notes) and
    the Training-Center mirror uses words instead of the 💪 emoji.
    """
    categories = rng.categories
    cat_by_key = {c.key: c for c in categories}
    duration_ids = {c.id for c in categories if c.type == "duration"}
    activities, matches = rng.activities, rng.matches

    text: dict[tuple[int, str], str] = {}
    colors: dict[tuple[int, str], str] = {}

    # Duration cells (sum minutes per category/day) + note/★ suffixes.
    # Pay-per-session coach sessions get the coach's name in the cell — the
    # exception worth seeing (the package coach is the unlabeled norm).
    per_session_names = {
        c.id: c.name
        for c in db.query(Coach).filter(Coach.counts_package.is_(False))
    }
    mins: dict[tuple[int, str], int] = {}
    cell_notes: dict[tuple[int, str], str] = {}  # per-cell activity note
    coach_labels: dict[tuple[int, str], str] = {}  # per-session coach name
    starts: set[tuple[int, str]] = set()  # cells whose day starts a package
    for a in activities:
        if a.category_id not in duration_ids:
            continue
        key = (a.category_id, a.date.isoformat())
        mins[key] = mins.get(key, 0) + (a.duration_minutes or 0)
        if a.note:
            cell_notes[key] = a.note
        if a.coach_id in per_session_names:
            coach_labels[key] = per_session_names[a.coach_id]
        if a.is_package_start:
            starts.add(key)
    for key, m in mins.items():
        cell = format_duration(m)
        if key in coach_labels:
            cell = f"{cell} · {coach_labels[key]}"
        if key in cell_notes:
            # Legacy per-session days carried the coach's name as the NOTE
            # (the retired 2026-08-13 rule) — with the label in place, a
            # name-only note would just stutter ("· Phi Vũ (Phi Vũ)").
            if _fold(cell_notes[key]) != _fold(coach_labels.get(key, "")):
                cell = f"{cell} ({cell_notes[key]})".strip()
        if key in starts:  # first session of a new 10-session coaching package
            cell = f"{cell} {PACKAGE_MARK}".strip()
        text[key] = cell

    # Match cells.
    by_cell: dict[tuple[int, str], list[Match]] = {}
    for mt in matches:
        by_cell.setdefault((mt.category_id, mt.date.isoformat()), []).append(mt)
    for key, ms in by_cell.items():
        text[key] = format_match_cell(ms)

    # Physical Training cells. Before the cutover: the legacy checklist (ticked
    # labels, yellow at >=70%). From the cutover forward: a read-only mirror of
    # the Training Center session done that day.
    physical = cat_by_key.get("physical_training")
    if physical is not None:
        for iso, keys in rng.checks_by_date.items():
            text[(physical.id, iso)] = format_physical_cell(keys)
            if physical_is_yellow(keys):
                colors[(physical.id, iso)] = "yellow"
        tc_prefix = "Training Center" if for_export else "💪"
        for iso, info in rng.tc_physical.items():
            text[(physical.id, iso)] = (
                f"{tc_prefix} {info['done']}/{info['total']} · {info['focus_vi']}"
            )
            if info["is_yellow"]:
                colors[(physical.id, iso)] = "yellow"

    # Racket Time cells: auto-computed (coach + partner + 5 min per match
    # set). The maps also feed the Overall coloring below — computed once.
    r_training, r_playing = racket_minutes_by_day(categories, activities, matches)
    racket = cat_by_key.get("racket_time")
    if racket is not None:
        for iso in set(r_training) | set(r_playing):
            total = r_training.get(iso, 0) + r_playing.get(iso, 0)
            text[(racket.id, iso)] = format_duration(total)

    # Notes cells.
    notes_cat = cat_by_key.get("notes")
    if notes_cat is not None:
        for iso, note_text in rng.notes_by_date.items():
            text[(notes_cat.id, iso)] = (
                note_text if for_export else note_snippet(note_text)
            )

    # Overall: auto-generated colors from the day's data (not a manual rating).
    overall_colors = compute_overall_colors(
        categories,
        activities,
        matches,
        _physical_dates(rng),
        all_days=days,
        today=dt.date.today(),
        earliest=earliest_data_date(db),
        racket=(r_training, r_playing),
    )
    return text, colors, overall_colors


def build_week(
    db: Session, start: dt.date, end: dt.date | None = None
) -> schemas.WeekResponse:
    # The grid can span an arbitrary range (a single day, a week, a whole
    # month, …). Defaults to a 7-day Mon–Sun week when no end is given.
    if end is None:
        end = start + dt.timedelta(days=6)
    if end < start:
        end = start
    days = _date_range(start, end)

    rng = _load_range(db, start, end)
    categories = rng.categories
    cat_by_key = {c.key: c for c in categories}
    activities = rng.activities
    matches = rng.matches
    checks_by_date = rng.checks_by_date
    notes_by_date = rng.notes_by_date

    text, colors, overall_colors = _grid_cells(db, rng, days, for_export=False)
    cells: dict[str, schemas.CellData] = {
        f"{cid}|{iso}": schemas.CellData(
            display=display, color=colors.get((cid, iso))
        )
        for (cid, iso), display in text.items()
    }
    overall = cat_by_key.get("overall")
    if overall is not None:
        for iso, color in overall_colors.items():
            cells[f"{overall.id}|{iso}"] = schemas.CellData(display="", color=color)

    match_outs = _annotate_elo(db, matches)

    return schemas.WeekResponse(
        start=start,
        days=days,
        categories=[schemas.CategoryOut.model_validate(c) for c in categories],
        activities=[schemas.ActivityOut.model_validate(a) for a in activities],
        matches=match_outs,
        cells=cells,
        physical_checks=checks_by_date,
        day_notes=notes_by_date,
        physical_cutover=training_service.get_cutover(db),
    )
