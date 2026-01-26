"""Unit tests for API response models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.shared.api.response_models import (
    Balance,
    Fill,
    Forecast,
    ForecastPeriod,
    Market,
    Observation,
    Order,
    Orderbook,
    OrderbookLevel,
    Position,
)


class TestForecastPeriod:
    """Test suite for ForecastPeriod model."""

    def test_forecast_period_creation(self) -> None:
        """Test creating a ForecastPeriod instance."""
        period = ForecastPeriod(
            number=1,
            name="Tonight",
            start_time=datetime(2026, 1, 25, 18, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 1, 26, 6, 0, tzinfo=timezone.utc),
            is_daytime=False,
            temperature=32,
            temperature_unit="F",
            wind_speed="5 mph",
            wind_direction="NW",
            short_forecast="Clear",
            detailed_forecast="Clear skies with light winds.",
        )

        assert period.number == 1
        assert period.name == "Tonight"
        assert period.temperature == 32
        assert period.is_daytime is False

    def test_forecast_period_validation_error(self) -> None:
        """Test ForecastPeriod validation with missing required fields."""
        with pytest.raises(ValidationError):
            ForecastPeriod(
                number=1,
                name="Tonight",
                # Missing required fields
            )


class TestForecast:
    """Test suite for Forecast model."""

    def test_forecast_creation(self) -> None:
        """Test creating a Forecast instance."""
        now = datetime.now(timezone.utc)
        forecast = Forecast(
            updated=now,
            units="us",
            forecast_generator="BaselineForecast",
            generated_at=now,
            update_time=now,
            periods=[
                ForecastPeriod(
                    number=1,
                    name="Tonight",
                    start_time=now,
                    end_time=now,
                    is_daytime=False,
                    temperature=32,
                    wind_speed="5 mph",
                    wind_direction="NW",
                    short_forecast="Clear",
                    detailed_forecast="Clear skies.",
                )
            ],
        )

        assert forecast.units == "us"
        assert len(forecast.periods) == 1
        assert forecast.periods[0].temperature == 32


class TestObservation:
    """Test suite for Observation model."""

    def test_observation_creation(self) -> None:
        """Test creating an Observation instance."""
        obs = Observation(
            timestamp=datetime.now(timezone.utc),
            text_description="Partly Cloudy",
            temperature=20.5,
            dewpoint=15.0,
            wind_direction=180,
            wind_speed=10.5,
            relative_humidity=65.0,
        )

        assert obs.temperature == 20.5
        assert obs.dewpoint == 15.0
        assert obs.wind_direction == 180

    def test_observation_value_extraction(self) -> None:
        """Test extraction of values from NWS value objects."""
        obs = Observation(
            timestamp=datetime.now(timezone.utc),
            temperature={"value": 20.5, "unitCode": "wmoUnit:degC"},
            dewpoint={"value": 15.0, "unitCode": "wmoUnit:degC"},
        )

        assert obs.temperature == 20.5
        assert obs.dewpoint == 15.0

    def test_observation_null_values(self) -> None:
        """Test Observation with null values."""
        obs = Observation(
            timestamp=datetime.now(timezone.utc),
            temperature=None,
            dewpoint=None,
        )

        assert obs.temperature is None
        assert obs.dewpoint is None


class TestMarket:
    """Test suite for Market model."""

    def test_market_creation(self) -> None:
        """Test creating a Market instance."""
        market = Market(
            ticker="HIGHNYC-25JAN26",
            event_ticker="HIGHNYC",
            title="Will NYC high be above 32F?",
            yes_bid=45,
            yes_ask=48,
            no_bid=52,
            no_ask=55,
            volume=1000,
            open_interest=5000,
            status="open",
        )

        assert market.ticker == "HIGHNYC-25JAN26"
        assert market.yes_bid == 45
        assert market.yes_ask == 48
        assert market.status == "open"

    def test_market_spread_calculation(self) -> None:
        """Test market spread calculation."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test Market",
            yes_bid=45,
            yes_ask=48,
            status="open",
        )

        assert market.spread_cents == 3

    def test_market_spread_none_when_no_pricing(self) -> None:
        """Test spread returns None when pricing unavailable."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test Market",
            status="open",
        )

        assert market.spread_cents is None

    def test_market_mid_price(self) -> None:
        """Test mid price calculation."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test Market",
            yes_bid=45,
            yes_ask=48,
            status="open",
        )

        assert market.mid_price == 46.5

    def test_market_mid_price_none_when_no_pricing(self) -> None:
        """Test mid price returns None when pricing unavailable."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test Market",
            status="open",
        )

        assert market.mid_price is None


class TestOrderbookLevel:
    """Test suite for OrderbookLevel model."""

    def test_orderbook_level_creation(self) -> None:
        """Test creating an OrderbookLevel instance."""
        level = OrderbookLevel(price=45, quantity=100)

        assert level.price == 45
        assert level.quantity == 100


class TestOrderbook:
    """Test suite for Orderbook model."""

    def test_orderbook_creation(self) -> None:
        """Test creating an Orderbook instance."""
        orderbook = Orderbook(
            yes=[
                OrderbookLevel(price=45, quantity=100),
                OrderbookLevel(price=44, quantity=200),
            ],
            no=[
                OrderbookLevel(price=55, quantity=100),
                OrderbookLevel(price=56, quantity=200),
            ],
        )

        assert len(orderbook.yes) == 2
        assert len(orderbook.no) == 2

    def test_orderbook_best_yes_bid(self) -> None:
        """Test best yes bid calculation."""
        orderbook = Orderbook(
            yes=[
                OrderbookLevel(price=45, quantity=100),
                OrderbookLevel(price=44, quantity=200),
            ]
        )

        assert orderbook.best_yes_bid == 45

    def test_orderbook_best_yes_ask(self) -> None:
        """Test best yes ask calculation."""
        orderbook = Orderbook(
            yes=[
                OrderbookLevel(price=45, quantity=100),
                OrderbookLevel(price=46, quantity=200),
            ]
        )

        assert orderbook.best_yes_ask == 45

    def test_orderbook_empty_levels(self) -> None:
        """Test orderbook with empty levels."""
        orderbook = Orderbook()

        assert orderbook.best_yes_bid is None
        assert orderbook.best_yes_ask is None


class TestOrder:
    """Test suite for Order model."""

    def test_order_creation(self) -> None:
        """Test creating an Order instance."""
        order = Order(
            order_id="order_123",
            ticker="HIGHNYC-25JAN26",
            side="yes",
            action="buy",
            count=10,
            yes_price=45,
            status="resting",
            created_time=datetime.now(timezone.utc),
            filled_count=0,
        )

        assert order.order_id == "order_123"
        assert order.ticker == "HIGHNYC-25JAN26"
        assert order.side == "yes"
        assert order.count == 10

    def test_order_is_filled_property(self) -> None:
        """Test is_filled property."""
        order = Order(
            order_id="order_123",
            ticker="TEST-01",
            side="yes",
            action="buy",
            count=10,
            status="filled",
            created_time=datetime.now(timezone.utc),
            filled_count=10,
        )

        assert order.is_filled is True

    def test_order_is_not_filled_property(self) -> None:
        """Test is_filled property when partially filled."""
        order = Order(
            order_id="order_123",
            ticker="TEST-01",
            side="yes",
            action="buy",
            count=10,
            status="resting",
            created_time=datetime.now(timezone.utc),
            filled_count=5,
        )

        assert order.is_filled is False


class TestPosition:
    """Test suite for Position model."""

    def test_position_creation(self) -> None:
        """Test creating a Position instance."""
        position = Position(
            ticker="HIGHNYC-25JAN26",
            position=100,
            total_cost=4500,
            fees_paid=10,
        )

        assert position.ticker == "HIGHNYC-25JAN26"
        assert position.position == 100
        assert position.total_cost == 4500

    def test_position_average_price(self) -> None:
        """Test average price calculation."""
        position = Position(
            ticker="TEST-01",
            position=100,
            total_cost=4500,
        )

        assert position.average_price == 45.0

    def test_position_average_price_none_when_no_position(self) -> None:
        """Test average price returns None when no position."""
        position = Position(
            ticker="TEST-01",
            position=0,
            total_cost=0,
        )

        assert position.average_price is None


class TestFill:
    """Test suite for Fill model."""

    def test_fill_creation(self) -> None:
        """Test creating a Fill instance."""
        fill = Fill(
            fill_id="fill_123",
            order_id="order_123",
            ticker="HIGHNYC-25JAN26",
            side="yes",
            action="buy",
            count=10,
            yes_price=45,
            created_time=datetime.now(timezone.utc),
        )

        assert fill.fill_id == "fill_123"
        assert fill.order_id == "order_123"
        assert fill.count == 10

    def test_fill_price_property_yes_side(self) -> None:
        """Test price property for yes side."""
        fill = Fill(
            fill_id="fill_123",
            order_id="order_123",
            ticker="TEST-01",
            side="yes",
            action="buy",
            count=10,
            yes_price=45,
            created_time=datetime.now(timezone.utc),
        )

        assert fill.price == 45

    def test_fill_price_property_no_side(self) -> None:
        """Test price property for no side."""
        fill = Fill(
            fill_id="fill_123",
            order_id="order_123",
            ticker="TEST-01",
            side="no",
            action="buy",
            count=10,
            no_price=55,
            created_time=datetime.now(timezone.utc),
        )

        assert fill.price == 55

    def test_fill_notional_value(self) -> None:
        """Test notional value calculation."""
        fill = Fill(
            fill_id="fill_123",
            order_id="order_123",
            ticker="TEST-01",
            side="yes",
            action="buy",
            count=10,
            yes_price=45,
            created_time=datetime.now(timezone.utc),
        )

        assert fill.notional_value == 450


class TestBalance:
    """Test suite for Balance model."""

    def test_balance_creation(self) -> None:
        """Test creating a Balance instance."""
        balance = Balance(
            balance=10000,
            payout=500,
        )

        assert balance.balance == 10000
        assert balance.payout == 500

    def test_balance_available_balance(self) -> None:
        """Test available balance calculation."""
        balance = Balance(
            balance=10000,
            payout=500,
        )

        assert balance.available_balance == 9500

    def test_balance_no_payout(self) -> None:
        """Test balance with no pending payout."""
        balance = Balance(balance=10000)

        assert balance.available_balance == 10000
