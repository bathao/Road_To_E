"""Seed / reconcile the default grid rows (categories) shown in the sheet.

The 'Overall' row is auto-generated (see service.compute_overall_colors), not
edited by hand, but it is still a category so it renders as a grid row.
"""
from sqlalchemy.orm import Session

from app.features.tracker.models import Activity, Category, Match

# (key, label, type, color_group). Order here = display order (sort_order).
DEFAULT_CATEGORIES = [
    ("train_with_coach", "Train with Coach", "duration", "green"),
    ("training_with_partner", "Training with Partner", "duration", "green"),
    ("serve", "Serve", "duration", "green"),
    ("physical_training", "Physical Training", "checklist", "yellow"),
    ("practice_match", "Practice Match", "match", "none"),
    ("official_match", "Official Match", "match", "none"),
    ("notes", "Notes", "note", "none"),
    ("overall", "Overall", "rating", "none"),
]


def seed_categories(db: Session) -> None:
    """Reconcile the category table to DEFAULT_CATEGORIES. Idempotent.

    - Removes categories no longer in the defaults (and their entries).
    - Inserts any missing categories.
    - Keeps label/type/color/sort_order in sync with the defaults.
    """
    desired_keys = {key for key, *_ in DEFAULT_CATEGORIES}
    existing = {c.key: c for c in db.query(Category).all()}
    changed = False

    # Drop categories that are no longer wanted, plus their dependent rows.
    for key, cat in list(existing.items()):
        if key not in desired_keys:
            db.query(Activity).filter(Activity.category_id == cat.id).delete()
            db.query(Match).filter(Match.category_id == cat.id).delete()
            db.delete(cat)
            del existing[key]
            changed = True

    # Insert missing / update existing to match the defaults.
    for order, (key, label, type_, color) in enumerate(DEFAULT_CATEGORIES):
        cat = existing.get(key)
        if cat is None:
            db.add(
                Category(
                    key=key,
                    label=label,
                    type=type_,
                    color_group=color,
                    sort_order=order,
                )
            )
            changed = True
        elif (
            cat.label != label
            or cat.type != type_
            or cat.color_group != color
            or cat.sort_order != order
        ):
            cat.label = label
            cat.type = type_
            cat.color_group = color
            cat.sort_order = order
            changed = True

    if changed:
        db.commit()
