"""Base repository class with common database operations."""

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from src.shared.config.logging import get_logger
from src.shared.db.connection import DatabaseManager
from src.shared.db.models import Base

logger = get_logger(__name__)

# Generic type for ORM models
T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations.

    Provides a consistent interface for database operations and ensures
    all methods return proper types with logging.
    """

    def __init__(self, db_manager: DatabaseManager, model_class: type[T]) -> None:
        """Initialize repository.

        Args:
            db_manager: Database manager instance
            model_class: SQLAlchemy model class for this repository
        """
        self._db = db_manager
        self._model_class = model_class
        self._table_name = model_class.__tablename__
        logger.debug("repository_initialized", table=self._table_name)

    @property
    def model_class(self) -> type[T]:
        """Get the model class for this repository."""
        return self._model_class

    def get_by_id(self, record_id: int) -> T | None:
        """Get record by primary key ID.

        Args:
            record_id: Primary key ID

        Returns:
            Model instance or None if not found
        """
        with self._db.session() as session:
            result = session.get(self._model_class, record_id)
            if result:
                # Detach from session for safe return
                session.expunge(result)
            return result

    def get_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        """Get all records with pagination.

        Args:
            limit: Maximum records to return
            offset: Number of records to skip

        Returns:
            List of model instances
        """
        with self._db.session() as session:
            stmt = select(self._model_class).limit(limit).offset(offset)
            results = list(session.execute(stmt).scalars().all())
            # Detach all from session
            for result in results:
                session.expunge(result)
            return results

    def save(self, instance: T) -> T:
        """Save a model instance (insert or update).

        Args:
            instance: Model instance to save

        Returns:
            Saved model instance with updated fields
        """
        with self._db.session() as session:
            merged = session.merge(instance)
            session.flush()
            session.refresh(merged)
            session.expunge(merged)
            logger.debug(
                "record_saved",
                table=self._table_name,
                id=getattr(merged, "id", None),
            )
            return merged

    def delete(self, record_id: int) -> bool:
        """Delete record by ID.

        Args:
            record_id: Primary key ID

        Returns:
            True if deleted, False if not found
        """
        with self._db.session() as session:
            instance = session.get(self._model_class, record_id)
            if instance:
                session.delete(instance)
                logger.debug("record_deleted", table=self._table_name, id=record_id)
                return True
            return False

    def count(self) -> int:
        """Count total records in table.

        Returns:
            Total record count
        """
        with self._db.session() as session:
            result = session.execute(
                text(f"SELECT COUNT(*) FROM ops.{self._table_name}")
            )
            row = result.fetchone()
            return row[0] if row else 0

    def exists(self, record_id: int) -> bool:
        """Check if record exists.

        Args:
            record_id: Primary key ID

        Returns:
            True if exists
        """
        return self.get_by_id(record_id) is not None

    def _get_session(self) -> Session:
        """Get a new database session.

        Note: Caller is responsible for closing the session.

        Returns:
            SQLAlchemy session
        """
        return self._db._session_factory()

    @staticmethod
    def _utc_now() -> datetime:
        """Get current UTC timestamp.

        Returns:
            Timezone-aware datetime in UTC
        """
        return datetime.now(timezone.utc)
