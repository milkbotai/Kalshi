"""Database connection manager with health checks and connection pooling."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

from src.shared.config.logging import get_logger
from src.shared.config.settings import get_settings

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database connections with pooling and health checks.
    
    Supports context manager protocol for automatic session cleanup.
    Configurable pool size and timeout from settings.
    """

    def __init__(self, database_url: str | None = None) -> None:
        """Initialize database manager.
        
        Args:
            database_url: Database connection string. If None, loads from settings.
        """
        settings = get_settings()
        self._database_url = database_url or settings.database_url
        
        # Create engine with connection pooling
        self._engine: Engine = create_engine(
            self._database_url,
            poolclass=QueuePool,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,  # Set to True for SQL debugging
        )
        
        # Create session factory
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
        )
        
        logger.info(
            "database_manager_initialized",
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
        )

    @property
    def engine(self) -> Engine:
        """Get SQLAlchemy engine.
        
        Returns:
            SQLAlchemy engine instance
        """
        return self._engine

    def health_check(self) -> bool:
        """Check if database is reachable.
        
        Returns:
            True if database connection successful, False otherwise
        """
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.debug("database_health_check_passed")
            return True
        except Exception as e:
            logger.error("database_health_check_failed", error=str(e))
            return False

    @contextmanager
    def session(self) -> Generator[Session, None, None]:
        """Provide a transactional scope for database operations.
        
        Yields:
            SQLAlchemy session
            
        Example:
            with db_manager.session() as session:
                session.add(model)
                session.commit()
        """
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        """Close all database connections and dispose of engine.
        
        Should be called during graceful shutdown.
        """
        logger.info("closing_database_connections")
        self._engine.dispose()


# Global database manager instance
_db_manager: DatabaseManager | None = None


def get_db() -> DatabaseManager:
    """Get or create global database manager instance.
    
    Returns:
        DatabaseManager singleton instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
