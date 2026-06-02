"""One-off importer for the 23 Mar - 3 May 2026 sheet (second screenshot).

Idempotent: clears tracker data in 2026-03-23..2026-05-03 first (does NOT touch
the already-imported May 4-31 block), then re-inserts. Run from backend/:

    .venv\\Scripts\\python scripts\\imports\\import_mar_apr2026.py

Mapping decided with the user:
- Serve is logged as a serve count; ~200 serves ~= 15 min, so 200->15, 100->8.
- "N sets (cty)" practice entries (no W/L) are skipped.
- "Wall Sit" row -> tick the Physical Training 'wall_sit' item on those days.
- Overall is auto-generated, so it is not imported.
- Empty footwork rows are skipped.
"""
import datetime as dt

from app.core.db import SessionLocal, init_db
from app.features.tracker.models import Activity, Category, Match, PhysicalCheck
from app.features.tracker import service


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
        SERVE = cats["serve"].id
        PRACTICE = cats["practice_match"].id
        OFFICIAL = cats["official_match"].id

        start, end = dt.date(2026, 3, 23), dt.date(2026, 5, 3)

        db.query(Activity).filter(Activity.date >= start, Activity.date <= end).delete()
        db.query(Match).filter(Match.date >= start, Match.date <= end).delete()
        db.query(PhysicalCheck).filter(
            PhysicalCheck.date >= start, PhysicalCheck.date <= end
        ).delete()
        db.commit()

        # ---- Train with Coach (1 hour each) ----
        # (date, note)
        coach = [
            ((3, 31), None),
            ((4, 2), "N"),
            ((4, 3), None),
            ((4, 7), None),
            ((4, 14), None),
            ((4, 16), None),
            ((4, 21), None),
            ((4, 23), None),
            ((4, 28), None),
            ((4, 29), None),
        ]
        for (mo, day), note in coach:
            db.add(Activity(date=dt.date(2026, mo, day), category_id=COACH,
                            duration_minutes=60, note=note))

        # ---- Serve (serve count -> minutes; ~200 serves ~= 15 min) ----
        serve = [((4, 3), 15), ((4, 7), 15), ((4, 29), 8)]
        for (mo, day), minutes in serve:
            db.add(Activity(date=dt.date(2026, mo, day), category_id=SERVE,
                            duration_minutes=minutes, note=None))

        # ---- Wall Sit -> Physical Training 'wall_sit' tick ----
        for mo, day in [(4, 16), (4, 20), (4, 21), (4, 22), (4, 28)]:
            db.add(PhysicalCheck(date=dt.date(2026, mo, day), item_key="wall_sit"))

        # ---- Matches ----
        order_counter: dict[tuple, int] = {}

        def add(d, cat_id, disc="singles", my=0, opp=0, event=None):
            key = (d, cat_id)
            idx = order_counter.get(key, 0)
            order_counter[key] = idx + 1
            ev = service.get_or_create_event(db, event) if event else None
            db.add(Match(
                date=d, category_id=cat_id, discipline=disc,
                best_of=best_of_for(my, opp), my_sets=my, opp_sets=opp,
                event_id=ev.id if ev else None,
                is_nonplaying=False, nonplaying_label=None, order_index=idx,
            ))

        def MD(mo, day):
            return dt.date(2026, mo, day)

        # Practice Match (10/8 sets-cty entries skipped)
        add(MD(3, 23), PRACTICE, "doubles", 3, 1)
        add(MD(3, 23), PRACTICE, "singles", 3, 1)
        add(MD(3, 23), PRACTICE, "singles", 3, 2)
        add(MD(3, 25), PRACTICE, "singles", 3, 0)
        add(MD(3, 25), PRACTICE, "singles", 3, 0)
        add(MD(3, 25), PRACTICE, "singles", 3, 1)
        add(MD(3, 25), PRACTICE, "singles", 2, 3)
        add(MD(3, 25), PRACTICE, "singles", 0, 3)
        # 26 Mar: only "sets (cty)" -> skipped entirely
        add(MD(3, 30), PRACTICE, "singles", 3, 2)
        add(MD(3, 31), PRACTICE, "doubles", 3, 0)
        add(MD(3, 31), PRACTICE, "doubles", 3, 1)
        add(MD(3, 31), PRACTICE, "singles", 0, 3)
        add(MD(4, 2), PRACTICE, "doubles", 3, 2)
        add(MD(4, 2), PRACTICE, "singles", 1, 3)
        add(MD(4, 2), PRACTICE, "singles", 0, 3)
        add(MD(4, 6), PRACTICE, "singles", 0, 3)
        add(MD(4, 6), PRACTICE, "singles", 2, 3)
        add(MD(4, 6), PRACTICE, "singles", 3, 1)
        add(MD(4, 6), PRACTICE, "doubles", 0, 3)
        add(MD(4, 12), PRACTICE, "singles", 1, 2)
        add(MD(4, 12), PRACTICE, "singles", 0, 3)
        add(MD(4, 12), PRACTICE, "singles", 1, 3)
        add(MD(4, 16), PRACTICE, "singles", 3, 1)
        add(MD(4, 16), PRACTICE, "singles", 2, 3)
        add(MD(4, 23), PRACTICE, "singles", 3, 1)
        add(MD(4, 23), PRACTICE, "singles", 3, 2)
        add(MD(4, 23), PRACTICE, "singles", 3, 2)
        add(MD(4, 23), PRACTICE, "singles", 0, 3)

        # Official Match
        add(MD(3, 31), OFFICIAL, "singles", 2, 3)
        add(MD(3, 31), OFFICIAL, "singles", 1, 3)
        add(MD(4, 1), OFFICIAL, "singles", 1, 3)
        add(MD(4, 1), OFFICIAL, "singles", 2, 3)
        add(MD(4, 7), OFFICIAL, "singles", 0, 3)
        add(MD(4, 7), OFFICIAL, "singles", 1, 3)
        add(MD(4, 12), OFFICIAL, "doubles", 3, 2, event="Mai Lượng")
        add(MD(4, 12), OFFICIAL, "doubles", 2, 3, event="Mai Lượng")
        add(MD(4, 14), OFFICIAL, "doubles", 1, 3)
        add(MD(4, 14), OFFICIAL, "singles", 0, 3)
        add(MD(4, 14), OFFICIAL, "singles", 1, 3)
        add(MD(4, 14), OFFICIAL, "singles", 0, 3)
        add(MD(4, 14), OFFICIAL, "singles", 2, 3)
        add(MD(4, 18), OFFICIAL, "singles", 3, 1, event="Giải Vi Mạch")
        add(MD(4, 18), OFFICIAL, "singles", 3, 0, event="Giải Vi Mạch")
        add(MD(4, 18), OFFICIAL, "singles", 2, 3, event="Giải Vi Mạch")
        add(MD(4, 18), OFFICIAL, "singles", 0, 3, event="Giải Vi Mạch")
        add(MD(4, 19), OFFICIAL, "doubles", 2, 3, event="Giải Đồng đội 185")
        add(MD(4, 19), OFFICIAL, "singles", 3, 0, event="Giải Đồng đội 185")
        add(MD(4, 21), OFFICIAL, "singles", 1, 3)
        add(MD(4, 21), OFFICIAL, "singles", 0, 3)
        add(MD(4, 28), OFFICIAL, "singles", 0, 3)
        add(MD(4, 28), OFFICIAL, "singles", 2, 3)
        add(MD(5, 2), OFFICIAL, "singles", 3, 2, event="Giải FS (Third prize)")
        add(MD(5, 2), OFFICIAL, "singles", 3, 2, event="Giải FS (Third prize)")
        add(MD(5, 2), OFFICIAL, "doubles", 3, 2, event="Giải FS (Third prize)")
        add(MD(5, 2), OFFICIAL, "doubles", 3, 2, event="Giải FS (Third prize)")
        add(MD(5, 2), OFFICIAL, "doubles", 1, 3, event="Giải FS (Third prize)")
        add(MD(5, 2), OFFICIAL, "doubles", 2, 3, event="Giải FS (Third prize)")

        db.commit()

        acts = db.query(Activity).filter(Activity.date >= start, Activity.date <= end).count()
        mts = db.query(Match).filter(Match.date >= start, Match.date <= end).count()
        phys = db.query(PhysicalCheck).filter(
            PhysicalCheck.date >= start, PhysicalCheck.date <= end
        ).count()
        print(f"Imported (23 Mar - 3 May): {acts} duration entries, "
              f"{mts} matches, {phys} physical checks.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
