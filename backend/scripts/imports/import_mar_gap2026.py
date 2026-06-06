"""One-off importer for the 9-22 Mar 2026 gap (fourth screenshot).

Fills the previously-empty 9-22 Mar window between the 1-8 Mar block and the
23 Mar+ block. Idempotent: clears tracker data in 2026-03-09..2026-03-22 first,
then re-inserts. Run from backend/:

    .venv\\Scripts\\python scripts\\imports\\import_mar_gap2026.py

Mapping decided with the user:
- "1 hour" duration cells -> 60 minutes.
- "Backhand with Partner" green row -> the 'training_with_partner' category,
  with note "Backhand" to preserve the original label.
- "D:" prefix marks the immediately-following score group as doubles; the rest
  of a cell is singles.
- "BBTV Team Cup" (22 Mar) is kept as the event for that day's official matches.
- Overall is auto-generated, so it is not imported.
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
        PARTNER = cats["training_with_partner"].id
        PRACTICE = cats["practice_match"].id
        OFFICIAL = cats["official_match"].id

        start, end = dt.date(2026, 3, 9), dt.date(2026, 3, 22)

        db.query(Activity).filter(Activity.date >= start, Activity.date <= end).delete()
        db.query(Match).filter(Match.date >= start, Match.date <= end).delete()
        db.query(PhysicalCheck).filter(
            PhysicalCheck.date >= start, PhysicalCheck.date <= end
        ).delete()
        db.commit()

        def MD(day):
            return dt.date(2026, 3, day)

        # ---- Train with Coach (1 hour each) ----
        for day in (12, 13, 17):
            db.add(Activity(date=MD(day), category_id=COACH, duration_minutes=60))

        # ---- Backhand with Partner -> Training with Partner (1 hour each) ----
        for day in (16, 18):
            db.add(Activity(date=MD(day), category_id=PARTNER,
                            duration_minutes=60, note="Backhand"))

        # ---- Matches ----
        order_counter: dict[tuple, int] = {}

        def add(day, cat_id, disc="singles", my=0, opp=0, event=None):
            key = (day, cat_id)
            idx = order_counter.get(key, 0)
            order_counter[key] = idx + 1
            ev = service.get_or_create_event(db, event) if event else None
            db.add(Match(
                date=MD(day), category_id=cat_id, discipline=disc,
                best_of=best_of_for(my, opp), my_sets=my, opp_sets=opp,
                event_id=ev.id if ev else None,
                is_nonplaying=False, nonplaying_label=None, order_index=idx,
            ))

        # ---- Practice Match ----
        add(10, PRACTICE, "singles", 3, 0)
        add(10, PRACTICE, "singles", 3, 2)
        add(12, PRACTICE, "doubles", 2, 3)
        add(13, PRACTICE, "singles", 3, 1)
        add(13, PRACTICE, "singles", 0, 3)
        add(13, PRACTICE, "singles", 0, 3)
        add(18, PRACTICE, "singles", 3, 1)
        add(18, PRACTICE, "singles", 3, 2)
        add(18, PRACTICE, "singles", 1, 3)
        add(18, PRACTICE, "singles", 2, 3)
        add(19, PRACTICE, "singles", 3, 1)
        add(19, PRACTICE, "singles", 2, 1)
        add(19, PRACTICE, "singles", 2, 3)

        # ---- Official Match ----
        # 10 Mar: D: L(2-3) | L(0-3,0-3,0-3,1-3)
        add(10, OFFICIAL, "doubles", 2, 3)
        add(10, OFFICIAL, "singles", 0, 3)
        add(10, OFFICIAL, "singles", 0, 3)
        add(10, OFFICIAL, "singles", 0, 3)
        add(10, OFFICIAL, "singles", 1, 3)
        # 12 Mar: D: L(0-3) | W(3-1,3-2) | L(0-3,1-3)
        add(12, OFFICIAL, "doubles", 0, 3)
        add(12, OFFICIAL, "singles", 3, 1)
        add(12, OFFICIAL, "singles", 3, 2)
        add(12, OFFICIAL, "singles", 0, 3)
        add(12, OFFICIAL, "singles", 1, 3)
        # 13 Mar: L(1-3, 0-3)
        add(13, OFFICIAL, "singles", 1, 3)
        add(13, OFFICIAL, "singles", 0, 3)
        # 17 Mar: W(3-0,3-1,3-2) | L(0-3) | D: L(1-3)
        add(17, OFFICIAL, "singles", 3, 0)
        add(17, OFFICIAL, "singles", 3, 1)
        add(17, OFFICIAL, "singles", 3, 2)
        add(17, OFFICIAL, "singles", 0, 3)
        add(17, OFFICIAL, "doubles", 1, 3)
        # 19 Mar: W(3-0) | D: L(2-3)
        add(19, OFFICIAL, "singles", 3, 0)
        add(19, OFFICIAL, "doubles", 2, 3)
        # 20 Mar: L(0-3,0-3,2-3) | W(3-2)
        add(20, OFFICIAL, "singles", 0, 3)
        add(20, OFFICIAL, "singles", 0, 3)
        add(20, OFFICIAL, "singles", 2, 3)
        add(20, OFFICIAL, "singles", 3, 2)
        # 22 Mar: BBTV Team Cup | D: L(2-3) | L(0-3,0-3)
        add(22, OFFICIAL, "doubles", 2, 3, event="BBTV Team Cup")
        add(22, OFFICIAL, "singles", 0, 3, event="BBTV Team Cup")
        add(22, OFFICIAL, "singles", 0, 3, event="BBTV Team Cup")

        db.commit()

        acts = db.query(Activity).filter(Activity.date >= start, Activity.date <= end).count()
        mts = db.query(Match).filter(Match.date >= start, Match.date <= end).count()
        print(f"Imported (9-22 Mar): {acts} duration entries, {mts} matches.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
