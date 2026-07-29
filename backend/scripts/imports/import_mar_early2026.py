"""One-off importer for the early-March 2026 portion (third screenshot).

Only the March days (1-8 Mar) of the 23 Feb - 8 Mar block are imported; the
February part is skipped per the user. Idempotent for 2026-03-01..2026-03-08
(does NOT touch the 23-31 Mar block imported earlier). Run from backend/:

    .venv\\Scripts\\python scripts\\imports\\import_mar_early2026.py

Mapping:
- "BBTV League Group1 / W1 L4" (7 Mar) -> 5 singles matches (1 win + 4 losses)
  with placeholder set scores (3-0 / 0-3) so it counts in win/loss stats.
- Overall is auto-generated, not imported.
"""
import sys
from pathlib import Path

# Make `app` importable when run as a plain script (sys.path[0] is this dir).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import datetime as dt  # noqa: E402

from app.core.db import SessionLocal, init_db  # noqa: E402
from app.features.tracker.models import Activity, Category, Match, PhysicalCheck  # noqa: E402
from app.features.tracker import service  # noqa: E402


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

        start, end = dt.date(2026, 3, 1), dt.date(2026, 3, 8)

        db.query(Activity).filter(Activity.date >= start, Activity.date <= end).delete()
        db.query(Match).filter(Match.date >= start, Match.date <= end).delete()
        db.query(PhysicalCheck).filter(
            PhysicalCheck.date >= start, PhysicalCheck.date <= end
        ).delete()
        db.commit()

        def MD(day):
            return dt.date(2026, 3, day)

        # Train with Coach
        for day in (3, 5):
            db.add(Activity(date=MD(day), category_id=COACH, duration_minutes=60))

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

        # Practice Match
        add(3, PRACTICE, "singles", 3, 2)
        add(4, PRACTICE, "singles", 1, 3)
        add(4, PRACTICE, "singles", 0, 3)
        add(4, PRACTICE, "singles", 2, 3)
        add(4, PRACTICE, "singles", 3, 2)
        add(5, PRACTICE, "singles", 2, 3)
        add(8, PRACTICE, "singles", 0, 4)
        add(8, PRACTICE, "singles", 0, 3)
        add(8, PRACTICE, "singles", 1, 3)
        add(8, PRACTICE, "doubles", 3, 2)

        # Official Match
        add(4, OFFICIAL, "singles", 1, 3)
        add(4, OFFICIAL, "singles", 2, 3)
        add(5, OFFICIAL, "singles", 0, 3)
        add(5, OFFICIAL, "singles", 2, 3)
        # 7 Mar: BBTV League Group1, W1 L4 (placeholder set scores 3-0 / 0-3)
        add(7, OFFICIAL, "singles", 3, 0, event="BBTV League Group1")
        for _ in range(4):
            add(7, OFFICIAL, "singles", 0, 3, event="BBTV League Group1")

        db.commit()

        acts = db.query(Activity).filter(Activity.date >= start, Activity.date <= end).count()
        mts = db.query(Match).filter(Match.date >= start, Match.date <= end).count()
        print(f"Imported (1-8 Mar): {acts} duration entries, {mts} matches.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
