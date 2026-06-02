"""Business logic for the tracker tab: formatting, week aggregation, export."""
from __future__ import annotations

import csv
import datetime as dt
import io

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.features.tracker import schemas
from app.features.tracker.models import (
    Activity,
    Category,
    DayNote,
    Event,
    Match,
    PhysicalCheck,
)

# ---------------------------------------------------------------- physical items

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
# The Physical Training cell turns yellow once at least this share is ticked.
PHYSICAL_YELLOW_RATIO = 0.7


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
    """Render ticked items as their labels, one per line."""
    return "\n".join(PHYSICAL_ITEM_LABELS.get(k, k) for k in item_keys)


def physical_is_yellow(item_keys: list[str]) -> bool:
    if not PHYSICAL_ITEMS:
        return False
    return len(item_keys) / len(PHYSICAL_ITEMS) >= PHYSICAL_YELLOW_RATIO


# Max characters shown for a note in the (compact) grid cell.
_NOTE_SNIPPET_LEN = 22


def note_snippet(text: str) -> str:
    """A compact one-line preview for the grid cell ('📝 ...'). Full text lives
    in the editor / export."""
    s = " ".join((text or "").split())
    if len(s) > _NOTE_SNIPPET_LEN:
        s = s[:_NOTE_SNIPPET_LEN].rstrip() + "…"
    return f"📝 {s}".rstrip()


# ---------------------------------------------------------------- formatting


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


def _result_letter(my_sets: int, opp_sets: int) -> str:
    if my_sets > opp_sets:
        return "W"
    if my_sets < opp_sets:
        return "L"
    return "T"


# Fixed ordering of result groups within a cell.
_GROUP_ORDER = [
    ("singles", "W"),
    ("singles", "L"),
    ("singles", "T"),
    ("doubles", "W"),
    ("doubles", "L"),
    ("doubles", "T"),
]


def format_match_cell(matches: list[Match]) -> str:
    """Render a day's matches the way the Excel sheet shows them.

    e.g. 'W(3-0,3-1)' / 'D: L(2-3,1-3)', with event names and non-playing
    labels (Travel/Rest) on their own lines.
    """
    if not matches:
        return ""

    ordered = sorted(matches, key=lambda m: m.order_index)
    lines: list[str] = []

    # Non-playing markers (Travel / Rest).
    nonplaying: list[str] = []
    for m in ordered:
        if m.is_nonplaying and m.nonplaying_label and m.nonplaying_label not in nonplaying:
            nonplaying.append(m.nonplaying_label)

    # Event names (distinct, first-seen order).
    events: list[str] = []
    for m in ordered:
        if not m.is_nonplaying and m.event and m.event.name and m.event.name not in events:
            events.append(m.event.name)

    # Group scores by (discipline, result).
    groups: dict[tuple[str, str], list[str]] = {}
    for m in ordered:
        if m.is_nonplaying:
            continue
        key = (m.discipline, _result_letter(m.my_sets, m.opp_sets))
        groups.setdefault(key, []).append(f"{m.my_sets}-{m.opp_sets}")

    lines.extend(nonplaying)
    lines.extend(events)

    ordered_keys = _GROUP_ORDER + [k for k in groups if k not in _GROUP_ORDER]
    for key in ordered_keys:
        scores = groups.get(key)
        if not scores:
            continue
        discipline, result = key
        prefix = "D: " if discipline == "doubles" else ""
        lines.append(f"{prefix}{result}({','.join(scores)})")

    return "\n".join(lines)


def match_to_out(m: Match) -> schemas.MatchOut:
    return schemas.MatchOut(
        id=m.id,
        date=m.date,
        category_id=m.category_id,
        discipline=m.discipline,
        best_of=m.best_of,
        my_sets=m.my_sets,
        opp_sets=m.opp_sets,
        event_id=m.event_id,
        event_name=m.event.name if m.event else None,
        is_nonplaying=m.is_nonplaying,
        nonplaying_label=m.nonplaying_label,
        note=m.note,
        order_index=m.order_index,
    )


# ---------------------------------------------------------------- events


def get_or_create_event(db: Session, name: str | None) -> Event | None:
    name = (name or "").strip()
    if not name:
        return None
    event = db.query(Event).filter(Event.name == name).first()
    if event is None:
        event = Event(name=name)
        db.add(event)
        db.flush()
    return event


# ---------------------------------------------------------------- overall color


def earliest_data_date(db: Session) -> dt.date | None:
    """The first day that has any tracked data (for the red 'rest-day' bound)."""
    candidates = [
        db.query(func.min(Activity.date)).scalar(),
        db.query(func.min(Match.date)).scalar(),
        db.query(func.min(PhysicalCheck.date)).scalar(),
    ]
    dates = [d for d in candidates if d is not None]
    return min(dates) if dates else None


def compute_overall_colors(
    categories: list[Category],
    activities: list[Activity],
    matches: list[Match],
    physical_dates: set[str] | None = None,
    all_days: list[dt.date] | None = None,
    today: dt.date | None = None,
    earliest: dt.date | None = None,
) -> dict[str, str]:
    """Auto-generate the 'Overall' color per day (no manual rating).

    - green: any of the green-group rows (Train with Coach / Backhand with
      Partner / Serve) has duration data that day.
    - yellow: otherwise, any of the remaining rows (Physical Training, Practice
      Match, Official Match) has data that day.
    - red: a past day (>= the first tracked day, < today) with no data at all.
    - (absent): no data, and the day is today, in the future, or before tracking
      began.

    Returns {iso_date: 'green' | 'yellow' | 'red'}.
    """
    green_ids = {c.id for c in categories if c.color_group == "green"}

    green_days: set[str] = set()
    other_days: set[str] = set(physical_dates or set())

    for a in activities:
        if (a.duration_minutes or 0) <= 0:
            continue
        iso = a.date.isoformat()
        if a.category_id in green_ids:
            green_days.add(iso)
        else:
            other_days.add(iso)

    # Any match entry (including Travel/Rest) counts as activity for the day.
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


# ---------------------------------------------------------------- week


def build_week(db: Session, start: dt.date) -> schemas.WeekResponse:
    days = [start + dt.timedelta(days=i) for i in range(7)]
    end = days[-1]

    categories = db.query(Category).order_by(Category.sort_order).all()
    cat_by_key = {c.key: c for c in categories}

    activities = (
        db.query(Activity).filter(Activity.date >= start, Activity.date <= end).all()
    )
    matches = (
        db.query(Match)
        .filter(Match.date >= start, Match.date <= end)
        .order_by(Match.order_index)
        .all()
    )
    checks = (
        db.query(PhysicalCheck)
        .filter(PhysicalCheck.date >= start, PhysicalCheck.date <= end)
        .all()
    )
    checks_by_date = physical_checks_by_date(checks)
    notes = (
        db.query(DayNote).filter(DayNote.date >= start, DayNote.date <= end).all()
    )
    notes_by_date = {n.date.isoformat(): n.text for n in notes}

    cells: dict[str, schemas.CellData] = {}

    duration_ids = {c.id for c in categories if c.type == "duration"}

    # Duration cells (sum minutes per category/day).
    minutes: dict[str, int] = {}
    notes: dict[str, str] = {}
    for a in activities:
        if a.category_id not in duration_ids:
            continue
        k = f"{a.category_id}|{a.date.isoformat()}"
        minutes[k] = minutes.get(k, 0) + (a.duration_minutes or 0)
        if a.note:
            notes[k] = a.note
    for k, mins in minutes.items():
        text = format_duration(mins)
        if k in notes:
            text = f"{text} ({notes[k]})".strip()
        cells[k] = schemas.CellData(display=text)

    # Match cells.
    by_cell: dict[str, list[Match]] = {}
    for m in matches:
        by_cell.setdefault(f"{m.category_id}|{m.date.isoformat()}", []).append(m)
    for k, ms in by_cell.items():
        cells[k] = schemas.CellData(display=format_match_cell(ms))

    # Physical Training cells (checklist): show ticked labels, yellow at >=70%.
    physical = cat_by_key.get("physical_training")
    if physical is not None:
        for iso, keys in checks_by_date.items():
            cells[f"{physical.id}|{iso}"] = schemas.CellData(
                display=format_physical_cell(keys),
                color="yellow" if physical_is_yellow(keys) else None,
            )

    # Notes cells: compact 📝 preview; full text travels in day_notes.
    notes_cat = cat_by_key.get("notes")
    if notes_cat is not None:
        for iso, text in notes_by_date.items():
            cells[f"{notes_cat.id}|{iso}"] = schemas.CellData(
                display=note_snippet(text)
            )

    # Overall cells: auto-generated from the day's data (not a manual rating).
    overall = cat_by_key.get("overall")
    if overall is not None:
        colors = compute_overall_colors(
            categories,
            activities,
            matches,
            set(checks_by_date.keys()),
            all_days=days,
            today=dt.date.today(),
            earliest=earliest_data_date(db),
        )
        for iso, color in colors.items():
            cells[f"{overall.id}|{iso}"] = schemas.CellData(display="", color=color)

    return schemas.WeekResponse(
        start=start,
        days=days,
        categories=[schemas.CategoryOut.model_validate(c) for c in categories],
        activities=[schemas.ActivityOut.model_validate(a) for a in activities],
        matches=[match_to_out(m) for m in matches],
        cells=cells,
        physical_checks=checks_by_date,
        day_notes=notes_by_date,
    )


# ---------------------------------------------------------------- stats

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _blank_match_stats() -> dict:
    return {"total": 0, "wins": 0, "losses": 0, "ties": 0, "sets_won": 0, "sets_lost": 0}


def _finalize_match_stats(s: dict) -> schemas.MatchStats:
    decided = s["wins"] + s["losses"]
    win_rate = (s["wins"] / decided) if decided else None
    return schemas.MatchStats(**s, win_rate=win_rate)


def build_stats(db: Session, date_from: dt.date, date_to: dt.date) -> schemas.StatsResponse:
    dates = _date_range(date_from, date_to)
    iso_dates = [d.isoformat() for d in dates]

    categories = db.query(Category).order_by(Category.sort_order).all()
    duration_cats = [c for c in categories if c.type == "duration"]
    duration_ids = {c.id for c in duration_cats}

    activities = (
        db.query(Activity)
        .filter(Activity.date >= date_from, Activity.date <= date_to)
        .all()
    )
    matches = (
        db.query(Match)
        .filter(Match.date >= date_from, Match.date <= date_to)
        .all()
    )
    checks = (
        db.query(PhysicalCheck)
        .filter(PhysicalCheck.date >= date_from, PhysicalCheck.date <= date_to)
        .all()
    )

    # Per-day aggregates.
    minutes_per_day: dict[str, int] = {iso: 0 for iso in iso_dates}
    physical_per_day: dict[str, int] = {iso: 0 for iso in iso_dates}
    matches_per_day: dict[str, int] = {iso: 0 for iso in iso_dates}

    minutes_by_cat: dict[int, int] = {cid: 0 for cid in duration_ids}
    for a in activities:
        if a.category_id not in duration_ids or (a.duration_minutes or 0) <= 0:
            continue
        iso = a.date.isoformat()
        minutes_per_day[iso] = minutes_per_day.get(iso, 0) + a.duration_minutes
        minutes_by_cat[a.category_id] += a.duration_minutes

    for c in checks:
        iso = c.date.isoformat()
        physical_per_day[iso] = physical_per_day.get(iso, 0) + 1

    # Match stats (playing matches only), split by discipline.
    overall = _blank_match_stats()
    singles = _blank_match_stats()
    doubles = _blank_match_stats()

    for m in matches:
        if m.is_nonplaying:
            continue
        iso = m.date.isoformat()
        matches_per_day[iso] = matches_per_day.get(iso, 0) + 1

        bucket = doubles if m.discipline == "doubles" else singles
        for s in (overall, bucket):
            s["total"] += 1
            s["sets_won"] += m.my_sets
            s["sets_lost"] += m.opp_sets
            if m.my_sets > m.opp_sets:
                s["wins"] += 1
            elif m.my_sets < m.opp_sets:
                s["losses"] += 1
            else:
                s["ties"] += 1

    # Day-level counts.
    days_trained = sum(
        1
        for iso in iso_dates
        if minutes_per_day[iso] > 0
        or physical_per_day[iso] > 0
        or matches_per_day[iso] > 0
    )
    days_physical = sum(1 for iso in iso_dates if physical_per_day[iso] > 0)

    # In category display order (duration_cats already sorted by sort_order).
    minutes_by_category = [
        schemas.CategoryMinutes(
            key=c.key, label=c.label, minutes=minutes_by_cat.get(c.id, 0)
        )
        for c in duration_cats
    ]

    return schemas.StatsResponse(
        date_from=date_from,
        date_to=date_to,
        num_days=len(dates),
        days_trained=days_trained,
        days_physical=days_physical,
        minutes_total=sum(minutes_per_day.values()),
        minutes_by_category=minutes_by_category,
        overall=_finalize_match_stats(overall),
        singles=_finalize_match_stats(singles),
        doubles=_finalize_match_stats(doubles),
    )


# ---------------------------------------------------------------- breakdown


def _first_of_month(d: dt.date) -> dt.date:
    return d.replace(day=1)


def _next_month(d: dt.date) -> dt.date:
    return dt.date(d.year + (d.month // 12), (d.month % 12) + 1, 1)


def _last_of_month(d: dt.date) -> dt.date:
    return _next_month(d) - dt.timedelta(days=1)


def _bucket_ranges(date_from: dt.date, date_to: dt.date, unit: str):
    """Yield (key, label, b_from, b_to) sub-ranges that tile [from, to]."""
    if unit == "day":
        for d in _date_range(date_from, date_to):
            yield (d.isoformat(), f"{_WEEKDAYS[d.weekday()]} {d.day}", d, d)
        return
    if unit == "week":
        cur = date_from - dt.timedelta(days=date_from.weekday())  # Monday
        n = 0
        while cur <= date_to:
            n += 1
            w_end = cur + dt.timedelta(days=6)
            b_from = max(cur, date_from)
            b_to = min(w_end, date_to)
            yield (cur.isoformat(), f"Week {n}", b_from, b_to)
            cur = cur + dt.timedelta(days=7)
        return
    # default: month
    cur = _first_of_month(date_from)
    while cur <= date_to:
        m_end = _last_of_month(cur)
        b_from = max(cur, date_from)
        b_to = min(m_end, date_to)
        yield (cur.strftime("%Y-%m"), cur.strftime("%b"), b_from, b_to)
        cur = _next_month(cur)


def build_breakdown(
    db: Session, date_from: dt.date, date_to: dt.date, unit: str
) -> schemas.BreakdownResponse:
    """Per-sub-period metrics for the comparison bar chart."""
    activities = (
        db.query(Activity)
        .filter(Activity.date >= date_from, Activity.date <= date_to)
        .all()
    )
    matches = (
        db.query(Match).filter(Match.date >= date_from, Match.date <= date_to).all()
    )
    checks = (
        db.query(PhysicalCheck)
        .filter(PhysicalCheck.date >= date_from, PhysicalCheck.date <= date_to)
        .all()
    )
    duration_ids = {c.id for c in db.query(Category).filter(Category.type == "duration")}

    # Per-day aggregates.
    minutes: dict[str, int] = {}
    physical: set[str] = set()
    mcount: dict[str, int] = {}
    wins: dict[str, int] = {}
    losses: dict[str, int] = {}

    for a in activities:
        if a.category_id in duration_ids and (a.duration_minutes or 0) > 0:
            iso = a.date.isoformat()
            minutes[iso] = minutes.get(iso, 0) + a.duration_minutes
    for c in checks:
        physical.add(c.date.isoformat())
    for m in matches:
        if m.is_nonplaying:
            continue
        iso = m.date.isoformat()
        mcount[iso] = mcount.get(iso, 0) + 1
        if m.my_sets > m.opp_sets:
            wins[iso] = wins.get(iso, 0) + 1
        elif m.my_sets < m.opp_sets:
            losses[iso] = losses.get(iso, 0) + 1

    buckets: list[schemas.BreakdownBucket] = []
    for key, label, b_from, b_to in _bucket_ranges(date_from, date_to, unit):
        b_min = b_w = b_l = b_m = b_trained = b_phys = 0
        for d in _date_range(b_from, b_to):
            iso = d.isoformat()
            mins = minutes.get(iso, 0)
            mc = mcount.get(iso, 0)
            ph = iso in physical
            b_min += mins
            b_m += mc
            b_w += wins.get(iso, 0)
            b_l += losses.get(iso, 0)
            if ph:
                b_phys += 1
            if mins > 0 or ph or mc > 0:
                b_trained += 1
        decided = b_w + b_l
        buckets.append(
            schemas.BreakdownBucket(
                key=key,
                label=label,
                date_from=b_from,
                date_to=b_to,
                minutes=b_min,
                days_trained=b_trained,
                days_physical=b_phys,
                matches=b_m,
                wins=b_w,
                losses=b_l,
                win_rate=(b_w / decided) if decided else None,
            )
        )

    return schemas.BreakdownResponse(unit=unit, buckets=buckets)


# ---------------------------------------------------------------- export

_RATING_HEX = {"green": "FF63BE7B", "yellow": "FFFFEB84", "red": "FFE06666"}
_COLOR_HEX = {"green": "FF92D050", "yellow": "FFFFFF00", "none": None}


def _date_range(date_from: dt.date, date_to: dt.date) -> list[dt.date]:
    n = (date_to - date_from).days
    return [date_from + dt.timedelta(days=i) for i in range(n + 1)]


def _build_grid(db: Session, date_from: dt.date, date_to: dt.date):
    """Return (categories, dates, cell_text, rating_by_date, cell_colors)."""
    dates = _date_range(date_from, date_to)
    categories = db.query(Category).order_by(Category.sort_order).all()
    cat_by_key = {c.key: c for c in categories}
    duration_ids = {c.id for c in categories if c.type == "duration"}

    activities = (
        db.query(Activity)
        .filter(Activity.date >= date_from, Activity.date <= date_to)
        .all()
    )
    matches = (
        db.query(Match)
        .filter(Match.date >= date_from, Match.date <= date_to)
        .order_by(Match.order_index)
        .all()
    )
    checks = (
        db.query(PhysicalCheck)
        .filter(PhysicalCheck.date >= date_from, PhysicalCheck.date <= date_to)
        .all()
    )
    checks_by_date = physical_checks_by_date(checks)
    day_notes = (
        db.query(DayNote).filter(DayNote.date >= date_from, DayNote.date <= date_to).all()
    )

    text: dict[tuple[int, str], str] = {}
    cell_colors: dict[tuple[int, str], str] = {}

    mins: dict[tuple[int, str], int] = {}
    for a in activities:
        if a.category_id not in duration_ids:
            continue
        key = (a.category_id, a.date.isoformat())
        mins[key] = mins.get(key, 0) + (a.duration_minutes or 0)
    for key, m in mins.items():
        text[key] = format_duration(m)

    by_cell: dict[tuple[int, str], list[Match]] = {}
    for mt in matches:
        by_cell.setdefault((mt.category_id, mt.date.isoformat()), []).append(mt)
    for key, ms in by_cell.items():
        text[key] = format_match_cell(ms)

    # Physical Training checklist cells (text + yellow fill at >=70%).
    physical = cat_by_key.get("physical_training")
    if physical is not None:
        for iso, keys in checks_by_date.items():
            text[(physical.id, iso)] = format_physical_cell(keys)
            if physical_is_yellow(keys):
                cell_colors[(physical.id, iso)] = "yellow"

    # Notes cells: export the full text (not the truncated grid preview).
    notes_cat = cat_by_key.get("notes")
    if notes_cat is not None:
        for n in day_notes:
            text[(notes_cat.id, n.date.isoformat())] = n.text

    # Overall row colors are auto-generated, matching the on-screen grid.
    rating_by_date = compute_overall_colors(
        categories,
        activities,
        matches,
        set(checks_by_date.keys()),
        all_days=dates,
        today=dt.date.today(),
        earliest=earliest_data_date(db),
    )
    return categories, dates, text, rating_by_date, cell_colors


def export_csv(db: Session, date_from: dt.date, date_to: dt.date) -> bytes:
    categories, dates, text, rating_by_date, _colors = _build_grid(
        db, date_from, date_to
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Category", *[d.isoformat() for d in dates]])
    for c in categories:
        row = [c.label]
        for d in dates:
            iso = d.isoformat()
            if c.key == "overall":
                row.append(rating_by_date.get(iso, ""))
            else:
                row.append(text.get((c.id, iso), "").replace("\n", " | "))
        writer.writerow(row)
    return buf.getvalue().encode("utf-8-sig")


def export_xlsx(db: Session, date_from: dt.date, date_to: dt.date) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    categories, dates, text, rating_by_date, cell_colors = _build_grid(
        db, date_from, date_to
    )

    wb = Workbook()
    ws = wb.active
    ws.title = "Daily Tracker"

    header_font = Font(bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")

    ws.cell(row=1, column=1, value="Category").font = header_font
    for j, d in enumerate(dates, start=2):
        cell = ws.cell(row=1, column=j, value=d.strftime("%a %d %b %Y"))
        cell.font = header_font

    for i, c in enumerate(categories, start=2):
        label_cell = ws.cell(row=i, column=1, value=c.label)
        label_cell.font = header_font
        hex_color = _COLOR_HEX.get(c.color_group)
        if hex_color:
            label_cell.fill = PatternFill("solid", fgColor=hex_color)
        for j, d in enumerate(dates, start=2):
            iso = d.isoformat()
            cell = ws.cell(row=i, column=j)
            if c.key == "overall":
                rating = rating_by_date.get(iso)
                if rating and rating in _RATING_HEX:
                    cell.fill = PatternFill("solid", fgColor=_RATING_HEX[rating])
            else:
                cell.value = text.get((c.id, iso), "")
                cell.alignment = wrap
                fill = cell_colors.get((c.id, iso))
                if fill and fill in _RATING_HEX:
                    cell.fill = PatternFill("solid", fgColor=_RATING_HEX[fill])

    ws.column_dimensions["A"].width = 26
    for col in range(2, len(dates) + 2):
        ws.column_dimensions[ws.cell(row=1, column=col).column_letter].width = 18

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
