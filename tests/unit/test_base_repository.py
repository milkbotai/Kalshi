"""Tests for BaseRepository class."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session


class TestBaseRepository:
    """Tests for BaseRepository CRUD operations."""

    def test_init_sets_attributes(self) -> None:
        """Test repository initialization."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        # Create a mock model class
        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_db = MagicMock()

        repo = BaseRepository(mock_db, mock_model)

        assert repo._db is mock_db
        assert repo._model_class is mock_model
        assert repo._table_name == "test_table"

    def test_model_class_property(self) -> None:
        """Test model_class property returns the model class."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"
        mock_db = MagicMock()

        repo = BaseRepository(mock_db, mock_model)

        # Line 41: return self._model_class
        assert repo.model_class is mock_model

    def test_get_by_id_found(self) -> None:
        """Test get_by_id when record exists."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_session = MagicMock(spec=Session)
        mock_result = MagicMock()
        mock_session.get.return_value = mock_result

        mock_db = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)

        repo = BaseRepository(mock_db, mock_model)

        # Lines 52-57: get_by_id with found record
        result = repo.get_by_id(1)

        assert result is mock_result
        mock_session.get.assert_called_once_with(mock_model, 1)
        mock_session.expunge.assert_called_once_with(mock_result)

    def test_get_by_id_not_found(self) -> None:
        """Test get_by_id when record doesn't exist."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_session = MagicMock(spec=Session)
        mock_session.get.return_value = None

        mock_db = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)

        repo = BaseRepository(mock_db, mock_model)

        result = repo.get_by_id(999)

        assert result is None
        mock_session.expunge.assert_not_called()

    @patch("src.shared.db.repositories.base.select")
    def test_get_all_returns_list(self, mock_select: MagicMock) -> None:
        """Test get_all returns paginated list."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_result1 = MagicMock()
        mock_result2 = MagicMock()

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_result1, mock_result2]

        mock_execute = MagicMock()
        mock_execute.scalars.return_value = mock_scalars

        mock_session = MagicMock(spec=Session)
        mock_session.execute.return_value = mock_execute

        mock_db = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock the select chain
        mock_stmt = MagicMock()
        mock_stmt.limit.return_value.offset.return_value = mock_stmt
        mock_select.return_value = mock_stmt

        repo = BaseRepository(mock_db, mock_model)

        # Lines 69-75: get_all with results
        results = repo.get_all(limit=10, offset=5)

        assert len(results) == 2
        assert mock_session.expunge.call_count == 2

    def test_save_merges_and_returns(self) -> None:
        """Test save merges instance and returns it."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_instance = MagicMock()
        mock_merged = MagicMock()
        mock_merged.id = 42

        mock_session = MagicMock(spec=Session)
        mock_session.merge.return_value = mock_merged

        mock_db = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)

        repo = BaseRepository(mock_db, mock_model)

        # Lines 86-96: save
        result = repo.save(mock_instance)

        assert result is mock_merged
        mock_session.merge.assert_called_once_with(mock_instance)
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(mock_merged)
        mock_session.expunge.assert_called_once_with(mock_merged)

    def test_delete_found(self) -> None:
        """Test delete when record exists."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_instance = MagicMock()
        mock_session = MagicMock(spec=Session)
        mock_session.get.return_value = mock_instance

        mock_db = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)

        repo = BaseRepository(mock_db, mock_model)

        # Lines 107-113: delete with found record
        result = repo.delete(1)

        assert result is True
        mock_session.delete.assert_called_once_with(mock_instance)

    def test_delete_not_found(self) -> None:
        """Test delete when record doesn't exist."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_session = MagicMock(spec=Session)
        mock_session.get.return_value = None

        mock_db = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)

        repo = BaseRepository(mock_db, mock_model)

        result = repo.delete(999)

        assert result is False
        mock_session.delete.assert_not_called()

    def test_count_returns_count(self) -> None:
        """Test count returns total records."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_result = MagicMock()
        mock_result.fetchone.return_value = (42,)

        mock_session = MagicMock(spec=Session)
        mock_session.execute.return_value = mock_result

        mock_db = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)

        repo = BaseRepository(mock_db, mock_model)

        # Lines 121-126: count
        result = repo.count()

        assert result == 42

    def test_count_returns_zero_when_no_row(self) -> None:
        """Test count returns 0 when no row returned."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None

        mock_session = MagicMock(spec=Session)
        mock_session.execute.return_value = mock_result

        mock_db = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)

        repo = BaseRepository(mock_db, mock_model)

        result = repo.count()

        assert result == 0

    def test_exists_true(self) -> None:
        """Test exists returns True when record found."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_session = MagicMock(spec=Session)
        mock_session.get.return_value = MagicMock()

        mock_db = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)

        repo = BaseRepository(mock_db, mock_model)

        # Line 137: exists
        result = repo.exists(1)

        assert result is True

    def test_exists_false(self) -> None:
        """Test exists returns False when record not found."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_session = MagicMock(spec=Session)
        mock_session.get.return_value = None

        mock_db = MagicMock()
        mock_db.session.return_value.__enter__ = MagicMock(return_value=mock_session)
        mock_db.session.return_value.__exit__ = MagicMock(return_value=False)

        repo = BaseRepository(mock_db, mock_model)

        result = repo.exists(999)

        assert result is False

    def test_get_session_returns_session(self) -> None:
        """Test _get_session returns a new session."""
        from src.shared.db.repositories.base import BaseRepository
        from src.shared.db.models import Base

        mock_model = MagicMock(spec=Base)
        mock_model.__tablename__ = "test_table"

        mock_session = MagicMock(spec=Session)
        mock_db = MagicMock()
        mock_db._session_factory.return_value = mock_session

        repo = BaseRepository(mock_db, mock_model)

        # Line 147: _get_session
        result = repo._get_session()

        assert result is mock_session
        mock_db._session_factory.assert_called_once()

    def test_utc_now_returns_utc_datetime(self) -> None:
        """Test _utc_now returns timezone-aware UTC datetime."""
        from src.shared.db.repositories.base import BaseRepository

        # Line 156: _utc_now static method
        result = BaseRepository._utc_now()

        assert isinstance(result, datetime)
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc
