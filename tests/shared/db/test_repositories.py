"""Tests for repository pattern implementation.

Tests cover all repository classes with mock database sessions.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.shared.db.models import (
    Fill,
    MarketSnapshot,
    Order,
    OrderStatus,
    Position,
    Signal,
    WeatherSnapshot,
)
from src.shared.db.repositories import (
    FillRepository,
    MarketRepository,
    OrderRepository,
    PositionRepository,
    SignalRepository,
    WeatherRepository,
)
from src.shared.db.repositories.fill import FillCreate, FillModel
from src.shared.db.repositories.market import MarketSnapshotCreate, MarketSnapshotModel
from src.shared.db.repositories.order import OrderCreate, OrderModel
from src.shared.db.repositories.position import PositionCreate, PositionModel
from src.shared.db.repositories.signal import SignalCreate, SignalModel
from src.shared.db.repositories.weather import WeatherSnapshotCreate, WeatherSnapshotModel


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_manager():
    """Create a mock database manager."""
    manager = MagicMock()
    manager.session.return_value.__enter__ = MagicMock()
    manager.session.return_value.__exit__ = MagicMock()
    return manager


@pytest.fixture
def mock_session():
    """Create a mock SQLAlchemy session."""
    session = MagicMock()
    session.execute.return_value.scalars.return_value.all.return_value = []
    session.execute.return_value.scalar_one_or_none.return_value = None
    return session


# ============================================================================
# WeatherRepository Tests
# ============================================================================


class TestWeatherSnapshotModel:
    """Tests for WeatherSnapshotModel Pydantic model."""

    def test_from_orm_attributes(self):
        """Test Pydantic model can be created from ORM object."""
        now = datetime.now(timezone.utc)
        orm_obj = WeatherSnapshot(
            id=1,
            city_code="NYC",
            captured_at=now,
            forecast_high=75,
            forecast_low=60,
            current_temp=68.5,
            precipitation_probability=0.3,
            forecast_text="Partly cloudy",
            source="nws",
            is_stale=False,
            raw_forecast={"test": "data"},
            raw_observation=None,
            created_at=now,
        )

        model = WeatherSnapshotModel.model_validate(orm_obj)

        assert model.id == 1
        assert model.city_code == "NYC"
        assert model.forecast_high == 75
        assert model.forecast_low == 60
        assert model.current_temp == 68.5
        assert model.precipitation_probability == 0.3
        assert model.source == "nws"
        assert model.is_stale is False


class TestWeatherSnapshotCreate:
    """Tests for WeatherSnapshotCreate Pydantic model."""

    def test_create_minimal(self):
        """Test creating with minimal required fields."""
        data = WeatherSnapshotCreate(city_code="NYC")

        assert data.city_code == "NYC"
        assert data.forecast_high is None
        assert data.source == "nws"
        assert data.is_stale is False

    def test_create_full(self):
        """Test creating with all fields."""
        data = WeatherSnapshotCreate(
            city_code="LAX",
            forecast_high=85,
            forecast_low=65,
            current_temp=78.2,
            precipitation_probability=0.1,
            forecast_text="Sunny and warm",
            source="nws",
            is_stale=False,
            raw_forecast={"periods": []},
        )

        assert data.city_code == "LAX"
        assert data.forecast_high == 85
        assert data.raw_forecast == {"periods": []}


class TestWeatherRepository:
    """Tests for WeatherRepository class."""

    def test_init(self, mock_db_manager):
        """Test repository initialization."""
        repo = WeatherRepository(mock_db_manager)

        assert repo._db == mock_db_manager
        assert repo._model_class == WeatherSnapshot

    def test_save_snapshot(self, mock_db_manager):
        """Test saving a weather snapshot."""
        now = datetime.now(timezone.utc)

        # Create mock saved object
        saved_obj = WeatherSnapshot(
            id=1,
            city_code="NYC",
            captured_at=now,
            forecast_high=75,
            source="nws",
            is_stale=False,
            created_at=now,
        )

        mock_session = MagicMock()
        mock_session.merge.return_value = saved_obj
        mock_db_manager.session.return_value.__enter__.return_value = mock_session

        repo = WeatherRepository(mock_db_manager)

        data = WeatherSnapshotCreate(city_code="NYC", forecast_high=75)

        # Mock the save method to return the saved object
        with patch.object(repo, "save", return_value=saved_obj):
            result = repo.save_snapshot(data)

        assert isinstance(result, WeatherSnapshotModel)
        assert result.city_code == "NYC"
        assert result.forecast_high == 75


# ============================================================================
# MarketRepository Tests
# ============================================================================


class TestMarketSnapshotModel:
    """Tests for MarketSnapshotModel Pydantic model."""

    def test_spread_cents_property(self):
        """Test spread calculation."""
        now = datetime.now(timezone.utc)

        model = MarketSnapshotModel(
            id=1,
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            captured_at=now,
            yes_bid=45,
            yes_ask=48,
            volume=1000,
            open_interest=500,
            status="open",
            created_at=now,
        )

        assert model.spread_cents == 3

    def test_spread_cents_none_when_missing(self):
        """Test spread is None when prices missing."""
        now = datetime.now(timezone.utc)

        model = MarketSnapshotModel(
            id=1,
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            captured_at=now,
            yes_bid=None,
            yes_ask=None,
            volume=0,
            open_interest=0,
            status="open",
            created_at=now,
        )

        assert model.spread_cents is None

    def test_mid_price_property(self):
        """Test mid price calculation."""
        now = datetime.now(timezone.utc)

        model = MarketSnapshotModel(
            id=1,
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            captured_at=now,
            yes_bid=44,
            yes_ask=48,
            volume=0,
            open_interest=0,
            status="open",
            created_at=now,
        )

        assert model.mid_price == 46.0


class TestMarketSnapshotCreate:
    """Tests for MarketSnapshotCreate Pydantic model."""

    def test_create_minimal(self):
        """Test creating with minimal required fields."""
        data = MarketSnapshotCreate(
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
        )

        assert data.ticker == "HIGHNYC-26JAN26"
        assert data.city_code == "NYC"
        assert data.status == "open"
        assert data.volume == 0


# ============================================================================
# SignalRepository Tests
# ============================================================================


class TestSignalModel:
    """Tests for SignalModel Pydantic model."""

    def test_from_orm_attributes(self):
        """Test Pydantic model can be created from ORM object."""
        now = datetime.now(timezone.utc)
        orm_obj = Signal(
            id=1,
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            strategy_name="daily_high_temp",
            side="yes",
            decision="BUY",
            p_yes=0.65,
            uncertainty=0.1,
            edge=5.0,
            confidence=0.8,
            max_price=55.0,
            reason="Forecast above strike",
            features={"temp_diff": 5},
            trading_mode="shadow",
            created_at=now,
        )

        model = SignalModel.model_validate(orm_obj)

        assert model.id == 1
        assert model.ticker == "HIGHNYC-26JAN26"
        assert model.decision == "BUY"
        assert model.p_yes == 0.65
        assert model.edge == 5.0


class TestSignalCreate:
    """Tests for SignalCreate Pydantic model."""

    def test_p_yes_validation(self):
        """Test p_yes must be between 0 and 1."""
        # Valid values
        SignalCreate(
            ticker="TEST",
            city_code="NYC",
            strategy_name="test",
            decision="BUY",
            p_yes=0.5,
        )

        SignalCreate(
            ticker="TEST",
            city_code="NYC",
            strategy_name="test",
            decision="BUY",
            p_yes=0.0,
        )

        SignalCreate(
            ticker="TEST",
            city_code="NYC",
            strategy_name="test",
            decision="BUY",
            p_yes=1.0,
        )

        # Invalid values should raise
        with pytest.raises(ValueError):
            SignalCreate(
                ticker="TEST",
                city_code="NYC",
                strategy_name="test",
                decision="BUY",
                p_yes=-0.1,
            )

        with pytest.raises(ValueError):
            SignalCreate(
                ticker="TEST",
                city_code="NYC",
                strategy_name="test",
                decision="BUY",
                p_yes=1.1,
            )


# ============================================================================
# OrderRepository Tests
# ============================================================================


class TestOrderModel:
    """Tests for OrderModel Pydantic model."""

    def test_is_filled_property(self):
        """Test is_filled property."""
        now = datetime.now(timezone.utc)

        filled_model = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status=OrderStatus.FILLED.value,
            remaining_quantity=0,
            created_at=now,
            updated_at=now,
        )

        pending_model = OrderModel(
            id=2,
            intent_key="test-key-2",
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status=OrderStatus.PENDING.value,
            remaining_quantity=100,
            created_at=now,
            updated_at=now,
        )

        assert filled_model.is_filled is True
        assert pending_model.is_filled is False

    def test_is_open_property(self):
        """Test is_open property for various statuses."""
        now = datetime.now(timezone.utc)

        def make_order(status: str) -> OrderModel:
            return OrderModel(
                id=1,
                intent_key="test",
                ticker="TEST",
                city_code="NYC",
                side="yes",
                action="buy",
                quantity=100,
                limit_price=45.0,
                status=status,
                remaining_quantity=100,
                created_at=now,
                updated_at=now,
            )

        # Open statuses
        assert make_order(OrderStatus.PENDING.value).is_open is True
        assert make_order(OrderStatus.SUBMITTED.value).is_open is True
        assert make_order(OrderStatus.RESTING.value).is_open is True
        assert make_order(OrderStatus.PARTIALLY_FILLED.value).is_open is True

        # Closed statuses
        assert make_order(OrderStatus.FILLED.value).is_open is False
        assert make_order(OrderStatus.CANCELLED.value).is_open is False
        assert make_order(OrderStatus.REJECTED.value).is_open is False


class TestOrderCreate:
    """Tests for OrderCreate Pydantic model."""

    def test_quantity_must_be_positive(self):
        """Test quantity validation."""
        # Valid
        OrderCreate(
            intent_key="test",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=1,
            limit_price=45.0,
        )

        # Invalid
        with pytest.raises(ValueError):
            OrderCreate(
                intent_key="test",
                ticker="TEST",
                city_code="NYC",
                side="yes",
                quantity=0,
                limit_price=45.0,
            )

        with pytest.raises(ValueError):
            OrderCreate(
                intent_key="test",
                ticker="TEST",
                city_code="NYC",
                side="yes",
                quantity=-1,
                limit_price=45.0,
            )


class TestOrderRepository:
    """Tests for OrderRepository class."""

    def test_init(self, mock_db_manager):
        """Test repository initialization."""
        repo = OrderRepository(mock_db_manager)

        assert repo._db == mock_db_manager
        assert repo._model_class == Order


# ============================================================================
# FillRepository Tests
# ============================================================================


class TestFillModel:
    """Tests for FillModel Pydantic model."""

    def test_from_orm_attributes(self):
        """Test Pydantic model can be created from ORM object."""
        now = datetime.now(timezone.utc)
        orm_obj = Fill(
            id=1,
            order_id=10,
            kalshi_fill_id="fill-123",
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=50,
            price=45.0,
            notional_value=2250.0,
            fees=2.25,
            realized_pnl=100.0,
            trading_mode="shadow",
            fill_time=now,
            created_at=now,
        )

        model = FillModel.model_validate(orm_obj)

        assert model.id == 1
        assert model.order_id == 10
        assert model.quantity == 50
        assert model.price == 45.0
        assert model.notional_value == 2250.0


class TestFillCreate:
    """Tests for FillCreate Pydantic model."""

    def test_quantity_must_be_positive(self):
        """Test quantity validation."""
        # Valid
        FillCreate(
            order_id=1,
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=1,
            price=45.0,
        )

        # Invalid
        with pytest.raises(ValueError):
            FillCreate(
                order_id=1,
                ticker="TEST",
                city_code="NYC",
                side="yes",
                action="buy",
                quantity=0,
                price=45.0,
            )


# ============================================================================
# PositionRepository Tests
# ============================================================================


class TestPositionModel:
    """Tests for PositionModel Pydantic model."""

    def test_average_entry_price_property(self):
        """Test average entry price calculation."""
        now = datetime.now(timezone.utc)

        model = PositionModel(
            id=1,
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            side="yes",
            quantity=100,
            entry_price=45.0,
            total_cost=4500.0,
            opened_at=now,
            updated_at=now,
        )

        assert model.average_entry_price == 45.0

    def test_average_entry_price_none_when_zero_quantity(self):
        """Test average entry price is None when quantity is zero."""
        now = datetime.now(timezone.utc)

        model = PositionModel(
            id=1,
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            side="yes",
            quantity=0,
            entry_price=0.0,
            total_cost=0.0,
            opened_at=now,
            updated_at=now,
        )

        assert model.average_entry_price is None

    def test_is_long_and_is_short_properties(self):
        """Test position side properties."""
        now = datetime.now(timezone.utc)

        long_pos = PositionModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=100,
            opened_at=now,
            updated_at=now,
        )

        short_pos = PositionModel(
            id=2,
            ticker="TEST",
            city_code="NYC",
            side="no",
            quantity=100,
            opened_at=now,
            updated_at=now,
        )

        assert long_pos.is_long is True
        assert long_pos.is_short is False
        assert short_pos.is_long is False
        assert short_pos.is_short is True


class TestPositionCreate:
    """Tests for PositionCreate Pydantic model."""

    def test_quantity_must_be_non_negative(self):
        """Test quantity validation."""
        # Valid - zero is allowed for position creation
        PositionCreate(
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=0,
            entry_price=45.0,
        )

        PositionCreate(
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=100,
            entry_price=45.0,
        )


# ============================================================================
# Integration-style Tests (with mocked sessions)
# ============================================================================


class TestRepositoryIntegration:
    """Integration-style tests for repository pattern."""

    def test_weather_repository_get_latest(self, mock_db_manager):
        """Test WeatherRepository.get_latest method."""
        now = datetime.now(timezone.utc)

        # Create mock result
        mock_snapshot = WeatherSnapshot(
            id=1,
            city_code="NYC",
            captured_at=now,
            forecast_high=75,
            source="nws",
            is_stale=False,
            created_at=now,
        )

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = mock_snapshot
        mock_db_manager.session.return_value.__enter__.return_value = mock_session

        repo = WeatherRepository(mock_db_manager)
        result = repo.get_latest("NYC")

        assert result is not None
        assert isinstance(result, WeatherSnapshotModel)
        assert result.city_code == "NYC"
        assert result.forecast_high == 75

    def test_order_repository_create_idempotent_new(self, mock_db_manager):
        """Test OrderRepository.create_order_idempotent creates new order."""
        now = datetime.now(timezone.utc)

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        mock_db_manager.session.return_value.__enter__.return_value = mock_session

        repo = OrderRepository(mock_db_manager)

        data = OrderCreate(
            intent_key="NYC-12345-2024-01-26-BUY",
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            side="yes",
            quantity=100,
            limit_price=45.0,
        )

        # Mock save to return a saved order
        saved_order = Order(
            id=1,
            intent_key=data.intent_key,
            ticker=data.ticker,
            city_code=data.city_code,
            side=data.side,
            action="buy",
            quantity=data.quantity,
            limit_price=data.limit_price,
            status=OrderStatus.PENDING.value,
            filled_quantity=0,
            remaining_quantity=data.quantity,
            trading_mode="shadow",
            created_at=now,
            updated_at=now,
        )

        with patch.object(repo, "save", return_value=saved_order):
            with patch.object(repo, "get_by_intent_key", return_value=None):
                result, created = repo.create_order_idempotent(data)

        assert created is True
        assert isinstance(result, OrderModel)
        assert result.intent_key == data.intent_key

    def test_order_repository_create_idempotent_existing(self, mock_db_manager):
        """Test OrderRepository.create_order_idempotent returns existing order."""
        now = datetime.now(timezone.utc)

        existing_order = OrderModel(
            id=1,
            intent_key="NYC-12345-2024-01-26-BUY",
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=45.0,
            status=OrderStatus.PENDING.value,
            remaining_quantity=100,
            created_at=now,
            updated_at=now,
        )

        repo = OrderRepository(mock_db_manager)

        data = OrderCreate(
            intent_key="NYC-12345-2024-01-26-BUY",
            ticker="HIGHNYC-26JAN26",
            city_code="NYC",
            side="yes",
            quantity=100,
            limit_price=45.0,
        )

        with patch.object(repo, "get_by_intent_key", return_value=existing_order):
            result, created = repo.create_order_idempotent(data)

        assert created is False
        assert result.id == existing_order.id
        assert result.intent_key == existing_order.intent_key


# ============================================================================
# Schema and Migration Tests
# ============================================================================


class TestOpsSchema:
    """Tests for ops schema configuration."""

    def test_weather_snapshot_table_args(self):
        """Test WeatherSnapshot has correct table args."""
        assert WeatherSnapshot.__tablename__ == "weather_snapshots"
        assert WeatherSnapshot.__table_args__[-1] == {"schema": "ops"}

    def test_market_snapshot_table_args(self):
        """Test MarketSnapshot has correct table args."""
        assert MarketSnapshot.__tablename__ == "market_snapshots"
        assert MarketSnapshot.__table_args__[-1] == {"schema": "ops"}

    def test_signal_table_args(self):
        """Test Signal has correct table args."""
        assert Signal.__tablename__ == "signals"
        assert Signal.__table_args__[-1] == {"schema": "ops"}

    def test_order_table_args(self):
        """Test Order has correct table args."""
        assert Order.__tablename__ == "orders"
        assert Order.__table_args__[-1] == {"schema": "ops"}

    def test_fill_table_args(self):
        """Test Fill has correct table args."""
        assert Fill.__tablename__ == "fills"
        assert Fill.__table_args__[-1] == {"schema": "ops"}

    def test_position_table_args(self):
        """Test Position has correct table args."""
        assert Position.__tablename__ == "positions"
        assert Position.__table_args__[-1] == {"schema": "ops"}


class TestOrderIntentKeyUniqueness:
    """Tests for order intent_key uniqueness constraint."""

    def test_order_has_unique_intent_key_constraint(self):
        """Test Order model has unique constraint on intent_key."""
        # Check table args for unique constraint
        table_args = Order.__table_args__
        unique_constraints = [
            arg for arg in table_args
            if hasattr(arg, "name") and "intent_key" in str(arg)
        ]

        assert len(unique_constraints) >= 1
