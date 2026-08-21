"""Shared declarative base for all ORM models."""
import datetime as dt

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def utcnow() -> dt.datetime:
    """Shared `created_at` column default (was duplicated per feature)."""
    return dt.datetime.now(dt.timezone.utc)
