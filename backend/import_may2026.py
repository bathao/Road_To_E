"""One-off importer for the May 2026 sheet (from the user's screenshot).

Idempotent: clears any tracker data in 2026-05-04..2026-05-31 first, then
re-inserts. Run from the backend/ dir:

    .venv\\Scripts\\python import_may2026.py

Notes on the mapping (decided with the user):
- "Overall" is auto-generated, so it is not imported.
- "Other Training with Partner" (45m on 8 May) is skipped (row removed from app).
- Physical Training is now a checklist; historical physical days are marked by
  ticking all items (so the cell shows yellow = "did physical that day").
- Each score is one match; "D:" => doubles, else singles. W/L derives from sets.
- Travel / "Stiga (sub)" are non-playing entries; event names are kept.
"""
import datetime as dt

from app.core.db import SessionLocal, init_db
from app.features.tracker.models import Activity, Category, Match, PhysicalCheck
from app.features.tracker import service


def D(day: int) -> dt.date:
    return dt.date(2026, 5, day)


def best_of_for(my: int, opp: int) -> int:
    need = max(my, opp)
    if need <= 2:
        return 3
    if need <= 3:
        return 5
    return 7


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        cats = {c.key: c for c in db.query(Category).all()}
        COACH = cats["train_with_coach"].id
        PRACTICE = cats["practice_match"].id
        OFFICIAL = cats["official_match"].id
        PHYSICAL = cats["physical_training"].id

        start, end = D(4), D(31)

        # --- wipe the May range so re-runs don't duplicate ---
        db.query(Activity).filter(Activity.date >= start, Activity.date <= end).delete()
        db.query(Match).filter(Match.date >= start, Match.date <= end).delete()
        db.query(PhysicalCheck).filter(
            PhysicalCheck.date >= start, PhysicalCheck.date <= end
        ).delete()
        db.commit()

        # --- durations: Train with Coach ---
        # (day, minutes, note)
        coach = [
            (4, 60, None),
            (5, 60, "N"),
            (12, 60, None),
            (13, 120, None),
            (15, 120, None),
            (18, 120, None),
            (19, 120, None),
            (21, 60, None),
            (26, 30, None),
            (27, 45, None),
        ]
        for day, minutes, note in coach:
            db.add(Activity(date=D(day), category_id=COACH,
                            duration_minutes=minutes, note=note))

        # --- physical training: mark days as done (tick every item) ---
        physical_days = [16, 17, 18, 19, 27]
        all_items = [key for key, _ in service.PHYSICAL_ITEMS]
        for day in physical_days:
            for item in all_items:
                db.add(PhysicalCheck(date=D(day), item_key=item))

        # --- matches ---
        order_counter: dict[tuple, int] = {}

        def add(day, cat_id, disc="singles", my=0, opp=0, event=None, nonplaying=None):
            key = (day, cat_id)
            idx = order_counter.get(key, 0)
            order_counter[key] = idx + 1
            ev = service.get_or_create_event(db, event) if event else None
            db.add(Match(
                date=D(day), category_id=cat_id, discipline=disc,
                best_of=best_of_for(my, opp), my_sets=my, opp_sets=opp,
                event_id=ev.id if ev else None,
                is_nonplaying=bool(nonplaying), nonplaying_label=nonplaying,
                order_index=idx,
            ))

        # Practice Match
        add(4, PRACTICE, "singles", 3, 0)
        add(4, PRACTICE, "singles", 3, 1)
        add(9, PRACTICE, "singles", 3, 0)
        add(12, PRACTICE, "singles", 3, 2)
        add(13, PRACTICE, "doubles", 0, 3)
        # 20 May
        add(20, PRACTICE, "singles", 1, 0)
        add(20, PRACTICE, "singles", 3, 1)
        add(20, PRACTICE, "singles", 2, 0)
        add(20, PRACTICE, "singles", 0, 3)
        add(20, PRACTICE, "singles", 2, 3)
        add(20, PRACTICE, "singles", 0, 3)
        add(20, PRACTICE, "singles", 2, 3)
        # 26 May
        add(26, PRACTICE, "singles", 3, 2)
        add(26, PRACTICE, "singles", 1, 3)
        # 29 May
        add(29, PRACTICE, "singles", 1, 3)
        add(29, PRACTICE, "doubles", 3, 1)
        add(29, PRACTICE, "doubles", 1, 3)

        # Official Match
        add(4, OFFICIAL, "singles", 0, 3)
        add(4, OFFICIAL, "singles", 3, 1)
        add(5, OFFICIAL, "doubles", 2, 3)
        add(5, OFFICIAL, "singles", 0, 3)
        add(5, OFFICIAL, "singles", 1, 3)
        # 9 May - Ampere vs Marvell
        for my, opp in [(3, 1), (3, 1), (3, 2), (3, 0)]:
            add(9, OFFICIAL, "singles", my, opp, event="Ampere vs Marvell")
        # 10 May - BBTV Open
        for my, opp in [(3, 2), (3, 1), (3, 1)]:
            add(10, OFFICIAL, "singles", my, opp, event="BBTV Open")
        for my, opp in [(0, 3), (0, 3), (1, 3)]:
            add(10, OFFICIAL, "singles", my, opp, event="BBTV Open")
        for my, opp in [(3, 2), (3, 1)]:
            add(10, OFFICIAL, "doubles", my, opp, event="BBTV Open")
        for my, opp in [(2, 3), (1, 3)]:
            add(10, OFFICIAL, "doubles", my, opp, event="BBTV Open")
        # 12 May
        add(12, OFFICIAL, "singles", 3, 0)
        add(12, OFFICIAL, "singles", 2, 3)
        add(12, OFFICIAL, "singles", 0, 3)
        # 15 May
        add(15, OFFICIAL, "doubles", 0, 2)
        add(15, OFFICIAL, "doubles", 1, 3)
        # 18-19 May
        add(18, OFFICIAL, "singles", 0, 3)
        add(18, OFFICIAL, "singles", 1, 3)
        add(19, OFFICIAL, "singles", 1, 3)
        # 21 May
        add(21, OFFICIAL, "singles", 2, 3)
        add(21, OFFICIAL, "singles", 3, 1)
        # 22-25 May - Travel
        for day in [22, 23, 24, 25]:
            add(day, OFFICIAL, nonplaying="Travel")
        # 29-30 May
        add(29, OFFICIAL, "singles", 1, 3)
        add(30, OFFICIAL, nonplaying="Stiga (sub)")

        db.commit()

        # --- report ---
        acts = db.query(Activity).filter(Activity.date >= start, Activity.date <= end).count()
        mts = db.query(Match).filter(Match.date >= start, Match.date <= end).count()
        phys = db.query(PhysicalCheck).filter(
            PhysicalCheck.date >= start, PhysicalCheck.date <= end
        ).count()
        print(f"Imported: {acts} duration entries, {mts} matches, "
              f"{phys} physical checks ({len(physical_days)} physical days).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
