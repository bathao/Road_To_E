"""seed_categories must NEVER delete a category that fell out of the defaults,
nor any data hanging off it (user data must survive a code change)."""
from __future__ import annotations

import datetime as dt

from app.features.tracker import seed as tracker_seed
from app.features.tracker.seed import DEFAULT_CATEGORIES, seed_categories
from app.features.tracker.models import Activity, Category


def test_seed_keeps_orphan_category_and_its_data(db):
    orphan_key = "legacy_typo_row"
    assert orphan_key not in {key for key, *_ in DEFAULT_CATEGORIES}

    orphan = Category(key=orphan_key, label="Old Row", type="duration",
                      color_group="none", sort_order=42)
    db.add(orphan)
    db.commit()
    db.add(Activity(date=dt.date(2026, 7, 1), category_id=orphan.id,
                    duration_minutes=45))
    db.commit()
    orphan_id = orphan.id

    # Re-run the startup seed: it must reconcile defaults but keep the orphan.
    seed_categories(db)
    db.expire_all()

    kept = db.query(Category).filter(Category.key == orphan_key).first()
    assert kept is not None and kept.id == orphan_id
    acts = db.query(Activity).filter(Activity.category_id == orphan_id).all()
    assert len(acts) == 1 and acts[0].duration_minutes == 45

    # And the defaults themselves are all present exactly once.
    keys = [c.key for c in db.query(Category).all()]
    for key, *_ in DEFAULT_CATEGORIES:
        assert keys.count(key) == 1


def test_tracker_migrate_is_a_no_op_on_the_second_run(db):
    """The db fixture already ran migrate() once (via seed_categories). A
    second pass must find nothing to do — in particular the activity unique
    index must report "already there" instead of "created" every startup."""
    assert tracker_seed._ensure_activity_unique_index(db) is False
    tracker_seed.migrate(db)
    assert tracker_seed._ensure_activity_unique_index(db) is False
