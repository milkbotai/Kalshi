"""Base SQLAlchemy models and database configuration.

Provides declarative base class and common model mixins for all database models.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Naming convention for constraints
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.
    
    Provides metadata with naming conventions for constraints.
    """

    metadata = metadata


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamp columns.
    
    Automatically manages timestamps for record creation and updates.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc="Timestamp when record was created",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        doc="Timestamp when record was last updated",
    )


def utcnow() -> datetime:
    """Get current UTC timestamp.
    
    Returns:
        Current datetime in UTC timezone
    """
    return datetime.now(timezone.utc)
