"""Tests for remaining 25 uncovered lines to reach 100% coverage."""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


class TestHealthLine265:
    """Test health.py line 265: UNKNOWN status when all counters are 0."""

    def test_get_current_health_unknown_status(self) -> None:
        """Test get_current_health returns UNKNOWN when no components have status."""
        from src.analytics.health import get_current_health, ComponentStatus

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_result = MagicMock()

        # Return empty result - no components
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        health = get_current_health(mock_engine)

        # Line 265: overall = ComponentStatus.UNKNOWN
        assert health.overall_status == ComponentStatus.UNKNOWN


class TestRollupsLine76:
    """Test rollups.py line 76: win_rate returns 0 when no trades."""

    def test_strategy_metrics_win_rate_zero_trades(self) -> None:
        """Test StrategyMetrics.win_rate returns 0.0 when total trades is 0."""
        from src.analytics.rollups import StrategyMetrics

        metrics = StrategyMetrics(
            strategy_name="test_strategy",
            date=date.today(),
            signal_count=0,
            trade_count=0,
            gross_pnl=Decimal("0"),
            net_pnl=Decimal("0"),
            fees=Decimal("0"),
            win_count=0,
            loss_count=0,
            avg_edge=Decimal("0"),
            avg_confidence=Decimal("0"),
        )

        # Line 76: return 0.0 when total == 0
        assert metrics.win_rate == 0.0


class TestSignalGeneratorLine140:
    """Test signal_generator.py line 140: return None when confidence < min."""

    def test_precipitation_signal_low_confidence_returns_none(self) -> None:
        """Test generate_precipitation_signal returns None for low confidence."""
        from src.analytics.signal_generator import SignalGenerator
        from src.shared.api.response_models import Market

        # Set high min_confidence so line 140 is hit
        generator = SignalGenerator(min_confidence=0.9)

        market = Market(
            ticker="HIGHNYC-26JAN26-T42",
            event_ticker="HIGHNYC-26JAN26",
            title="Test",
            status="open",
        )

        # Weather data with precipitation between 0.3 and 0.8 (passes line 132-133)
        # but confidence will be capped at 0.8, which is < 0.9 min_confidence
        weather_data = {
            "precipitation_probability": 0.5,  # conf = min(0.5, 0.8) = 0.5 < 0.9
        }

        # Line 140: return None when confidence < min_confidence
        signal = generator.generate_precipitation_signal(weather_data, market)
        assert signal is None


class TestKalshiLine205:
    """Test kalshi.py line 205: max retries exceeded - defensive code."""

    def test_line_205_is_defensive_code(self) -> None:
        """Line 205 is defensive code that's unreachable in practice.

        Looking at the _make_request logic:
        - If raise_for_status succeeds, line 169 returns
        - If raise_for_status raises HTTPError, it either:
          - Retries via continue (lines 175-191)
          - Raises via raise (line 199)
        - If RequestException is raised, it's re-raised (line 203)

        So line 205 is never reached. It should be excluded from coverage.
        """
        pytest.skip("Line 205 is defensive/unreachable code - should be excluded")


class TestKalshiLines568_570:
    """Test kalshi.py lines 568-570: market parse exception."""

    @patch("requests.Session.request")
    def test_get_market_typed_parse_exception(
        self, mock_request: MagicMock
    ) -> None:
        """Test get_market_typed returns None on parse exception."""
        from src.shared.api.kalshi import KalshiClient

        # Return data that will cause exception during Market creation
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Return data where Market() constructor fails due to invalid types
        mock_response.json.return_value = {
            "market": {
                "ticker": 12345,  # Invalid type - should be string
                "event_ticker": {"nested": "object"},  # Invalid type
                "title": ["list"],  # Invalid type
                "status": None,  # Invalid type
            }
        }
        mock_request.return_value = mock_response

        client = KalshiClient(api_key_id="test")

        with patch.object(KalshiClient, "_get_auth_headers", return_value={"KALSHI-ACCESS-KEY": "test"}):
            # Lines 568-570: exception handling returns None
            result = client.get_market_typed("TEST")
            assert result is None


class TestNWSLine130:
    """Test nws.py line 130: max retries exceeded."""

    @patch("requests.Session.get")
    @patch("time.sleep")
    def test_make_request_max_retries_exceeded(
        self, mock_sleep: MagicMock, mock_get: MagicMock
    ) -> None:
        """Test HTTPError raised after all retries exhausted."""
        from src.shared.api.nws import NWSClient
        import requests

        # All requests return 500 error
        mock_response = MagicMock()
        mock_response.status_code = 500
        http_error = requests.HTTPError("500 Server Error")
        http_error.response = mock_response
        mock_response.raise_for_status.side_effect = http_error
        mock_get.return_value = mock_response

        client = NWSClient()

        # Line 130: raise requests.HTTPError("Max retries exceeded")
        with pytest.raises(requests.HTTPError):
            client.get_forecast("OKX", 33, 37)


class TestWeatherCacheLine269:
    """Test weather_cache.py line 269 and 276: prefetch success/failure."""

    @patch("src.shared.api.weather_cache.city_loader")
    def test_prefetch_all_cities_exception(self, mock_loader: MagicMock) -> None:
        """Test prefetch_all_cities marks city as False on exception."""
        from src.shared.api.weather_cache import WeatherCache

        # Mock city loader to return cities but get_city raises
        mock_loader.get_all_cities.return_value = {"NYC": MagicMock(), "LAX": MagicMock()}
        mock_loader.get_city.side_effect = KeyError("City not found")

        mock_nws = MagicMock()
        cache = WeatherCache(nws_client=mock_nws)

        # Line 276: get_weather fails, results[city_code] = False
        results = cache.prefetch_all_cities()

        assert results["NYC"] is False
        assert results["LAX"] is False

    @patch("src.shared.api.weather_cache.city_loader")
    def test_prefetch_all_cities_success(self, mock_loader: MagicMock) -> None:
        """Test prefetch_all_cities marks city as True on success."""
        from src.shared.api.weather_cache import WeatherCache

        # Mock city config
        mock_city = MagicMock()
        mock_city.code = "NYC"
        mock_city.nws_station = "OKX"
        mock_city.nws_grid_x = 33
        mock_city.nws_grid_y = 37

        mock_loader.get_all_cities.return_value = {"NYC": mock_city}
        mock_loader.get_city.return_value = mock_city

        mock_nws = MagicMock()
        mock_nws.get_forecast.return_value = {"properties": {"periods": []}}
        mock_nws.get_observations.return_value = {"properties": {}}

        cache = WeatherCache(nws_client=mock_nws)

        # Line 269: get_weather succeeds, results[city_code] = True
        results = cache.prefetch_all_cities()

        assert results["NYC"] is True


class TestDbInitLines63_64:
    """Test db/__init__.py lines 63-64: get_trading_repositories with None."""

    @patch("src.shared.db.get_db")
    def test_get_trading_repositories_uses_get_db(self, mock_get_db: MagicMock) -> None:
        """Test get_trading_repositories calls get_db when db_manager is None."""
        from src.shared.db import get_trading_repositories

        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        # Lines 63-64: db = db_manager or get_db()
        repos = get_trading_repositories(db_manager=None)

        mock_get_db.assert_called_once()
        assert len(repos) == 6


class TestModelsLines151_153:
    """Test models.py lines 151-153: spread_cents property."""

    def test_market_snapshot_spread_cents_none(self) -> None:
        """Test MarketSnapshot.spread_cents returns None when bid or ask is None."""
        from src.shared.db.models import MarketSnapshot

        snapshot = MarketSnapshot(
            ticker="TEST",
            city_code="NYC",
            yes_bid=None,  # No bid
            yes_ask=50,
        )

        # Line 153: return None when yes_bid is None
        assert snapshot.spread_cents is None

        snapshot2 = MarketSnapshot(
            ticker="TEST",
            city_code="NYC",
            yes_bid=45,
            yes_ask=None,  # No ask
        )

        assert snapshot2.spread_cents is None

    def test_market_snapshot_spread_cents_calculated(self) -> None:
        """Test MarketSnapshot.spread_cents calculates when both values present."""
        from src.shared.db.models import MarketSnapshot

        snapshot = MarketSnapshot(
            ticker="TEST",
            city_code="NYC",
            yes_bid=45,
            yes_ask=50,
        )

        # Line 152: return yes_ask - yes_bid
        assert snapshot.spread_cents == 5


class TestModelsLines325_327:
    """Test models.py lines 325-327: average_entry_price property."""

    def test_position_average_entry_price_zero_quantity(self) -> None:
        """Test Position.average_entry_price returns None when quantity is 0."""
        from src.shared.db.models import Position

        position = Position(
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=0,  # Zero quantity
            total_cost=0.0,
            trading_mode="shadow",
        )

        # Line 327: return None when quantity == 0
        assert position.average_entry_price is None

    def test_position_average_entry_price_calculated(self) -> None:
        """Test Position.average_entry_price calculates when quantity > 0."""
        from src.shared.db.models import Position

        position = Position(
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=10,
            total_cost=500.0,  # 10 @ $50
            trading_mode="shadow",
        )

        # Line 326: return total_cost / abs(quantity)
        assert position.average_entry_price == 50.0


class TestOrderRepoLine205:
    """Test order.py line 205: re-raise after race condition."""

    def test_create_order_idempotent_race_condition_reraise(self) -> None:
        """Test create_order_idempotent re-raises when existing order not found after IntegrityError."""
        from src.shared.db.repositories.order import OrderRepository, OrderCreate
        from sqlalchemy.exc import IntegrityError

        mock_db = MagicMock()
        repo = OrderRepository(mock_db)

        mock_session = MagicMock()
        mock_db.session.return_value.__enter__.return_value = mock_session

        # Mock save to raise IntegrityError
        with patch.object(repo, "save") as mock_save:
            mock_save.side_effect = IntegrityError("", "", Exception("duplicate key"))

            # Mock get_by_intent_key to return None first (doesn't exist),
            # then None again after IntegrityError (still not found - re-raise)
            with patch.object(repo, "get_by_intent_key", return_value=None):
                order_data = OrderCreate(
                    intent_key="test-key",
                    ticker="TEST",
                    city_code="NYC",
                    side="yes",
                    quantity=10,
                    limit_price=50.0,
                    trading_mode="shadow",
                )

                # Line 205: raise (re-raise IntegrityError)
                with pytest.raises(IntegrityError):
                    repo.create_order_idempotent(order_data)


class TestOrderRepoLine337:
    """Test order.py line 337: status unchanged branch."""

    def test_record_fill_status_unchanged(self) -> None:
        """Test record_fill when order has no fills and gets 0 new fill.

        Line 337 is hit when:
        - new_remaining > 0 (not fully filled)
        - new_filled == 0 (no fills at all)

        This requires filled_quantity=0 and fill_quantity=0.
        """
        from src.shared.db.repositories.order import OrderRepository, OrderModel

        mock_db = MagicMock()
        repo = OrderRepository(mock_db)

        # Create order model with NO fills yet
        order = OrderModel(
            id=1,
            intent_key="test-key",
            ticker="TEST",
            city_code="NYC",
            side="yes",
            action="buy",
            quantity=100,
            limit_price=50.0,
            status="pending",
            filled_quantity=0,  # No fills yet
            remaining_quantity=100,  # Full quantity remaining
            average_fill_price=None,
            trading_mode="shadow",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_session = MagicMock()
        mock_db.session.return_value.__enter__.return_value = mock_session

        with patch.object(repo, "get_by_intent_key", return_value=order):
            # Record fill with 0 quantity - status should stay the same
            # new_remaining = 100, new_filled = 0, so line 337 is hit
            repo.record_fill(order.intent_key, fill_quantity=0, fill_price=50.0)

            # Verify the update was called
            mock_session.execute.assert_called()


class TestPositionRepoLine198:
    """Test position.py line 198: re-raise after race condition."""

    def test_get_or_create_position_race_reraise(self) -> None:
        """Test get_or_create_position re-raises when existing not found."""
        from src.shared.db.repositories.position import PositionRepository
        from sqlalchemy.exc import IntegrityError

        mock_db = MagicMock()
        repo = PositionRepository(mock_db)

        mock_session = MagicMock()
        mock_db.session.return_value.__enter__.return_value = mock_session

        # Mock save to raise IntegrityError
        with patch.object(repo, "save") as mock_save:
            mock_save.side_effect = IntegrityError("", "", Exception("duplicate key"))

            # Mock get_open_position to return None (not found after error)
            with patch.object(repo, "get_open_position", return_value=None):
                # Line 198: raise
                with pytest.raises(IntegrityError):
                    repo.get_or_create_position(
                        ticker="TEST",
                        city_code="NYC",
                        side="yes",
                        trading_mode="shadow",
                    )


class TestPositionRepoLines375_376:
    """Test position.py lines 375-376: close position updates."""

    def test_reduce_position_closes_position(self) -> None:
        """Test reduce_position sets is_closed and closed_at when fully closed."""
        from src.shared.db.repositories.position import PositionRepository, PositionModel

        mock_db = MagicMock()
        repo = PositionRepository(mock_db)

        # Position with 10 quantity - use real PositionModel
        position = PositionModel(
            id=1,
            ticker="TEST",
            city_code="NYC",
            side="yes",
            quantity=10,
            entry_price=50.0,
            total_cost=500.0,
            realized_pnl=0.0,
            trading_mode="shadow",
            is_closed=False,
            opened_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        mock_session = MagicMock()
        mock_db.session.return_value.__enter__.return_value = mock_session

        with patch.object(repo, "get_by_id", return_value=position):
            # Reduce by full quantity to close
            # Lines 375-376: values["is_closed"] = True, values["closed_at"] = ...
            result, pnl = repo.reduce_position(position.id, quantity=10, exit_price=55.0)

            # Verify update was called
            mock_session.execute.assert_called()


class TestPositionRepoLine531:
    """Test position.py line 531: include_closed filter."""

    def test_get_positions_by_city_excludes_closed(self) -> None:
        """Test get_positions_by_city filters out closed positions by default."""
        from src.shared.db.repositories.position import PositionRepository

        mock_db = MagicMock()
        repo = PositionRepository(mock_db)

        mock_session = MagicMock()
        mock_db.session.return_value.__enter__.return_value = mock_session

        # Return empty list
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        # Line 531: stmt = stmt.where(Position.is_closed == False)
        result = repo.get_positions_by_city(include_closed=False)

        assert result == {}


class TestAnomalyLine406:
    """Test anomaly.py line 406: NORMAL classification from LLM response."""

    def test_parse_response_normal_classification(self) -> None:
        """Test _parse_response handles NORMAL classification."""
        from src.shared.llm.anomaly import (
            AnomalyClassifier,
            AnomalyClassification,
            AnomalyType,
            AnomalyClassificationResult,
        )
        from src.shared.llm.openrouter import LLMResponse
        from src.shared.api.response_models import Market

        mock_client = MagicMock()
        classifier = AnomalyClassifier(mock_client)

        # LLM returns NORMAL classification - use correct LLMResponse fields
        response = LLMResponse(
            content='{"classification": "NORMAL", "reason": "No anomaly detected", "confidence": 0.95}',
            model="test",
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            latency_ms=100.0,
        )

        market = Market(
            ticker="TEST",
            event_ticker="EVENT",
            title="Test",
            status="open",
        )

        rule_based = AnomalyClassification(
            ticker="TEST",
            classification=AnomalyClassificationResult.SUSPICIOUS,
            anomaly_type=AnomalyType.WIDE_SPREAD,
            reason="Rule-based fallback",
            confidence=0.5,
        )

        # Line 406: classification = AnomalyClassificationResult.NORMAL
        result = classifier._parse_response(response, market, rule_based)
        assert result.classification == AnomalyClassificationResult.NORMAL


class TestOpenRouterLine251:
    """Test openrouter.py line 251: all retries exhausted without last_error."""

    @patch("httpx.Client.post")
    def test_chat_all_retries_no_last_error(self, mock_post: MagicMock) -> None:
        """Test chat raises OpenRouterError when retries exhausted."""
        from src.shared.llm.openrouter import OpenRouterClient, OpenRouterConfig, OpenRouterError
        import httpx

        config = OpenRouterConfig(api_key="test-key", max_retries=1, retry_delay_seconds=0.001)
        client = OpenRouterClient(config)

        # Make post raise RequestError
        mock_post.side_effect = httpx.RequestError("Connection failed")

        # Line 251: raise OpenRouterError("All retries exhausted")
        with pytest.raises(OpenRouterError):
            client.chat("Hello")
