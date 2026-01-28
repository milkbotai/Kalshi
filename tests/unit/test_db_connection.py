"""Unit tests for database connection manager."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError

from src.shared.db.connection import DatabaseManager


class TestDatabaseManager:
    """Test suite for DatabaseManager."""

    def test_database_manager_initialization(self) -> None:
        """Test DatabaseManager initializes with settings."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")

            assert db_manager.engine == mock_engine
            mock_create_engine.assert_called_once()

    def test_health_check_success(self) -> None:
        """Test health check returns True when database is reachable."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_conn = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            mock_create_engine.return_value = mock_engine

            db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")
            result = db_manager.health_check()

            assert result is True
            mock_conn.execute.assert_called_once()

    def test_health_check_failure(self) -> None:
        """Test health check returns False when database is unreachable."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_engine.connect.side_effect = OperationalError("Connection failed", None, None)
            mock_create_engine.return_value = mock_engine

            db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")
            result = db_manager.health_check()

            assert result is False

    def test_session_context_manager(self) -> None:
        """Test session context manager commits on success."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            with patch("src.shared.db.connection.sessionmaker") as mock_sessionmaker:
                mock_session = MagicMock()
                mock_sessionmaker.return_value = MagicMock(return_value=mock_session)

                db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")

                with db_manager.session() as session:
                    assert session == mock_session

                mock_session.commit.assert_called_once()
                mock_session.close.assert_called_once()

    def test_session_context_manager_rollback_on_error(self) -> None:
        """Test session context manager rolls back on exception."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            with patch("src.shared.db.connection.sessionmaker") as mock_sessionmaker:
                mock_session = MagicMock()
                mock_sessionmaker.return_value = MagicMock(return_value=mock_session)

                db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")

                with pytest.raises(ValueError):
                    with db_manager.session():
                        raise ValueError("Test error")

                mock_session.rollback.assert_called_once()
                mock_session.close.assert_called_once()

    def test_close_disposes_engine(self) -> None:
        """Test close method disposes of engine."""
        with patch("src.shared.db.connection.create_engine") as mock_create_engine:
            mock_engine = MagicMock()
            mock_create_engine.return_value = mock_engine

            db_manager = DatabaseManager(database_url="postgresql://test:test@localhost/test")
            db_manager.close()

            mock_engine.dispose.assert_called_once()
