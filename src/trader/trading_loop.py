"""Trading loop implementation for single and multi-city trading.

Implements the main trading cycle: fetch weather → fetch markets →
evaluate strategy → check gates → submit orders.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from src.shared.api.kalshi import KalshiClient
from src.shared.api.response_models import Market
from src.shared.api.weather_cache import CachedWeather, WeatherCache, get_weather_cache
from src.shared.config.cities import CityConfig, city_loader
from src.shared.config.logging import get_logger
from src.shared.config.settings import TradingMode, get_settings
from src.trader.gates import check_all_gates
from src.trader.oms import OrderManagementSystem, OrderState
from src.trader.risk import CircuitBreaker, RiskCalculator
from src.trader.strategies.daily_high_temp import DailyHighTempStrategy
from src.trader.strategy import Signal

if TYPE_CHECKING:
    from src.shared.db.connection import DatabaseManager
    from src.shared.db.repositories import (
        MarketRepository,
        SignalRepository,
        WeatherRepository,
    )

logger = get_logger(__name__)


@dataclass
class TradingCycleResult:
    """Result of a single trading cycle.

    Contains summary statistics and details of what happened during the cycle.
    """

    city_code: str
    started_at: datetime
    completed_at: datetime
    weather_fetched: bool
    markets_fetched: int
    signals_generated: int
    gates_passed: int
    orders_submitted: int
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Check if cycle completed without errors."""
        return len(self.errors) == 0

    @property
    def duration_seconds(self) -> float:
        """Get cycle duration in seconds."""
        return (self.completed_at - self.started_at).total_seconds()


class TradingLoop:
    """Main trading loop for executing strategy across markets.

    Handles the complete trading cycle for a single city:
    1. Fetch weather data
    2. Fetch market data
    3. Evaluate strategy
    4. Check execution gates
    5. Submit orders (based on trading mode)
    """

    def __init__(
        self,
        kalshi_client: KalshiClient | None = None,
        weather_cache: WeatherCache | None = None,
        oms: OrderManagementSystem | None = None,
        risk_calculator: RiskCalculator | None = None,
        circuit_breaker: CircuitBreaker | None = None,
        strategy: DailyHighTempStrategy | None = None,
        trading_mode: TradingMode | None = None,
        db_manager: "DatabaseManager | None" = None,
        weather_repo: "WeatherRepository | None" = None,
        market_repo: "MarketRepository | None" = None,
        signal_repo: "SignalRepository | None" = None,
    ) -> None:
        """Initialize trading loop.

        Args:
            kalshi_client: Kalshi API client (created from settings if not provided)
            weather_cache: Weather cache instance
            oms: Order management system instance
            risk_calculator: Risk calculator instance
            circuit_breaker: Circuit breaker instance
            strategy: Trading strategy instance
            trading_mode: Trading mode override (uses settings if not provided)
            db_manager: Database manager for persistence (optional)
            weather_repo: Weather repository for persistence (optional)
            market_repo: Market repository for persistence (optional)
            signal_repo: Signal repository for persistence (optional)
        """
        settings = get_settings()

        self.trading_mode = trading_mode or settings.trading_mode
        self.weather_cache = weather_cache or get_weather_cache()
        self.oms = oms or OrderManagementSystem()
        self.risk_calculator = risk_calculator or RiskCalculator()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self.strategy = strategy or DailyHighTempStrategy()

        # Repository integration (optional - enables persistence)
        self.db_manager = db_manager
        self.weather_repo = weather_repo
        self.market_repo = market_repo
        self.signal_repo = signal_repo

        # Track if LIVE mode was explicitly confirmed
        self._live_mode_confirmed = False

        # Kalshi client - only create if not in SHADOW mode
        if kalshi_client:
            self.kalshi_client = kalshi_client
        elif self.trading_mode != TradingMode.SHADOW:
            self.kalshi_client = KalshiClient(
                api_key=settings.kalshi_api_key or "",
                api_secret=settings.kalshi_api_secret or "",
                base_url=settings.kalshi_api_url,
            )
        else:
            self.kalshi_client = None  # type: ignore[assignment]

        # Validate trading mode configuration
        self._validate_trading_mode(settings)

        logger.info(
            "trading_loop_initialized",
            trading_mode=self.trading_mode.value,
            strategy=self.strategy.name,
            is_live=self.trading_mode == TradingMode.LIVE,
        )

    def _validate_trading_mode(self, settings: Any) -> None:
        """Validate trading mode configuration.

        Args:
            settings: Application settings

        Raises:
            ValueError: If LIVE mode without proper configuration
        """
        if self.trading_mode == TradingMode.LIVE:
            # LIVE mode requires API credentials
            if not settings.kalshi_api_key or not settings.kalshi_api_secret:
                raise ValueError(
                    "LIVE mode requires KALSHI_API_KEY and KALSHI_API_SECRET"
                )

            # LIVE mode should use production URL
            if "demo" in (settings.kalshi_api_url or "").lower():
                logger.warning(
                    "live_mode_with_demo_url",
                    url=settings.kalshi_api_url,
                    message="LIVE mode configured but using demo API URL",
                )

        elif self.trading_mode == TradingMode.DEMO:
            # DEMO mode should use demo URL
            if "demo" not in (settings.kalshi_api_url or "").lower():
                logger.warning(
                    "demo_mode_with_production_url",
                    url=settings.kalshi_api_url,
                    message="DEMO mode configured but using production API URL",
                )

    def confirm_live_mode(self) -> bool:
        """Explicitly confirm LIVE mode trading.

        Must be called before any real money trades in LIVE mode.

        Returns:
            True if confirmed, False if not in LIVE mode

        Raises:
            ValueError: If LIVE mode not properly configured
        """
        if self.trading_mode != TradingMode.LIVE:
            return False

        if not self.kalshi_client:
            raise ValueError("LIVE mode requires Kalshi client")

        self._live_mode_confirmed = True
        logger.info(
            "live_mode_confirmed",
            message="LIVE trading mode has been explicitly confirmed",
            warning="Real money trades will be executed",
        )
        return True

    @property
    def is_live_trading_enabled(self) -> bool:
        """Check if live trading is enabled and confirmed."""
        return (
            self.trading_mode == TradingMode.LIVE
            and self._live_mode_confirmed
            and self.kalshi_client is not None
        )

    def run_cycle(
        self,
        city_code: str,
        quantity: int = 100,
    ) -> TradingCycleResult:
        """Run a single trading cycle for one city.

        Args:
            city_code: 3-letter city code
            quantity: Default trade quantity

        Returns:
            TradingCycleResult with cycle statistics
        """
        started_at = datetime.now(timezone.utc)
        errors: list[str] = []
        weather_fetched = False
        markets_fetched = 0
        signals_generated = 0
        gates_passed = 0
        orders_submitted = 0

        logger.info(
            "trading_cycle_started",
            city_code=city_code,
            trading_mode=self.trading_mode.value,
        )

        # Check circuit breaker
        if self.circuit_breaker.is_paused:
            errors.append(f"Trading paused: {self.circuit_breaker.pause_reason}")
            logger.warning(
                "trading_cycle_skipped_circuit_breaker",
                city_code=city_code,
                reason=self.circuit_breaker.pause_reason,
            )
            return TradingCycleResult(
                city_code=city_code,
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                weather_fetched=False,
                markets_fetched=0,
                signals_generated=0,
                gates_passed=0,
                orders_submitted=0,
                errors=errors,
            )

        # Step 1: Fetch weather
        try:
            city_config = city_loader.get_city(city_code)
            cached_weather = self.weather_cache.get_weather(city_code)
            weather_fetched = cached_weather.forecast is not None

            if cached_weather.is_stale:
                logger.warning("weather_data_stale", city_code=city_code)

            logger.debug(
                "weather_fetched",
                city_code=city_code,
                has_forecast=weather_fetched,
                is_stale=cached_weather.is_stale,
            )
        except Exception as e:
            errors.append(f"Weather fetch failed: {e}")
            logger.error("weather_fetch_error", city_code=city_code, error=str(e))
            cached_weather = None

        # Step 2: Fetch markets
        markets: list[Market] = []
        if self.kalshi_client and self.trading_mode != TradingMode.SHADOW:
            try:
                # Fetch markets for this city's high temp series
                series_ticker = f"HIGH{city_code}"
                markets = self.kalshi_client.get_markets_typed(
                    series_ticker=series_ticker,
                    status="open",
                )
                markets_fetched = len(markets)

                logger.debug(
                    "markets_fetched",
                    city_code=city_code,
                    count=markets_fetched,
                )
            except Exception as e:
                errors.append(f"Market fetch failed: {e}")
                logger.error("market_fetch_error", city_code=city_code, error=str(e))
        else:
            # SHADOW mode - no market fetching
            logger.debug("shadow_mode_no_market_fetch", city_code=city_code)

        # Step 3: Evaluate strategy for each market
        signals: list[tuple[Signal, Market, int | None]] = []
        weather_snapshot_id: int | None = None

        if cached_weather and cached_weather.forecast:
            # Build weather dict for strategy
            weather_data = self._build_weather_data(cached_weather.forecast, city_config)

            # Persist weather snapshot
            weather_snapshot_id = self._persist_weather(cached_weather, weather_data)

            for market in markets:
                # Persist market snapshot
                market_snapshot_id = self._persist_market(market, city_code)

                try:
                    signal = self.strategy.evaluate(weather_data, market)
                    signals_generated += 1

                    # Persist signal
                    signal_id = self._persist_signal(
                        signal,
                        market,
                        city_code,
                        weather_snapshot_id=weather_snapshot_id,
                        market_snapshot_id=market_snapshot_id,
                    )

                    signals.append((signal, market, signal_id))

                    logger.debug(
                        "signal_generated",
                        ticker=market.ticker,
                        decision=signal.decision,
                        p_yes=signal.p_yes,
                        edge=signal.edge,
                        signal_id=signal_id,
                    )
                except Exception as e:
                    errors.append(f"Strategy evaluation failed for {market.ticker}: {e}")
                    logger.error(
                        "strategy_evaluation_error",
                        ticker=market.ticker,
                        error=str(e),
                    )

        # Step 4: Check gates and submit orders
        for signal, market, _signal_id in signals:
            if signal.decision == "HOLD":
                continue

            # Check execution gates
            passed, failed_reasons = check_all_gates(
                signal=signal,
                market=market,
                quantity=quantity,
            )

            if not passed:
                logger.info(
                    "gates_failed_no_trade",
                    ticker=market.ticker,
                    reasons=failed_reasons,
                )
                continue

            gates_passed += 1

            # Check risk limits
            trade_risk = (quantity * (signal.max_price or 50)) / 100.0
            if not self.risk_calculator.check_trade_size(trade_risk, quantity):
                logger.info("trade_blocked_risk_limit", ticker=market.ticker)
                continue

            if not self.risk_calculator.check_city_exposure(
                city_code, trade_risk, []
            ):
                logger.info("trade_blocked_city_exposure", ticker=market.ticker)
                continue

            # Step 5: Submit order based on trading mode
            try:
                order = self._submit_order(signal, city_config, market, quantity)
                if order:
                    orders_submitted += 1
            except Exception as e:
                errors.append(f"Order submission failed for {market.ticker}: {e}")
                logger.error(
                    "order_submission_error",
                    ticker=market.ticker,
                    error=str(e),
                )

        completed_at = datetime.now(timezone.utc)

        result = TradingCycleResult(
            city_code=city_code,
            started_at=started_at,
            completed_at=completed_at,
            weather_fetched=weather_fetched,
            markets_fetched=markets_fetched,
            signals_generated=signals_generated,
            gates_passed=gates_passed,
            orders_submitted=orders_submitted,
            errors=errors,
        )

        logger.info(
            "trading_cycle_completed",
            city_code=city_code,
            duration_seconds=result.duration_seconds,
            weather_fetched=weather_fetched,
            markets_fetched=markets_fetched,
            signals_generated=signals_generated,
            gates_passed=gates_passed,
            orders_submitted=orders_submitted,
            errors_count=len(errors),
        )

        return result

    def _build_weather_data(
        self,
        forecast: dict[str, Any],
        city_config: CityConfig,
    ) -> dict[str, Any]:
        """Build weather data dictionary for strategy evaluation.

        Args:
            forecast: Raw forecast data from NWS
            city_config: City configuration

        Returns:
            Normalized weather data for strategy
        """
        weather_data: dict[str, Any] = {
            "city_code": city_config.code,
            "temperature": None,
            "forecast_std_dev": 3.0,  # Default uncertainty
        }

        # Extract high temperature from forecast periods
        periods = forecast.get("periods", [])
        if periods:
            # Find daytime period (usually first or second)
            for period in periods[:2]:
                if period.get("isDaytime", period.get("is_daytime", True)):
                    weather_data["temperature"] = period.get("temperature")
                    break

        return weather_data

    def _persist_weather(
        self,
        cached_weather: CachedWeather,
        weather_data: dict[str, Any],
    ) -> int | None:
        """Persist weather snapshot to repository if configured.

        Args:
            cached_weather: Cached weather data from API
            weather_data: Processed weather data for strategy

        Returns:
            Snapshot ID if saved, None if repositories not configured
        """
        if not self.weather_repo:
            return None

        try:
            from src.shared.db.repositories.weather import WeatherSnapshotCreate

            snapshot_data = WeatherSnapshotCreate(
                city_code=weather_data["city_code"],
                forecast_high=weather_data.get("temperature"),
                current_temp=None,  # Extract from observation if available
                is_stale=cached_weather.is_stale,
                raw_forecast=cached_weather.forecast,
                raw_observation=cached_weather.observation,
            )

            # Extract current temp from observation if available
            if cached_weather.observation:
                temp_data = cached_weather.observation.get("temperature", {})
                if isinstance(temp_data, dict) and temp_data.get("value") is not None:
                    snapshot_data.current_temp = float(temp_data["value"])

            saved = self.weather_repo.save_snapshot(snapshot_data)
            logger.debug(
                "weather_persisted",
                city_code=weather_data["city_code"],
                snapshot_id=saved.id,
            )
            return saved.id
        except Exception as e:
            logger.warning(
                "weather_persistence_failed",
                city_code=weather_data["city_code"],
                error=str(e),
            )
            return None

    def _persist_market(
        self,
        market: Market,
        city_code: str,
    ) -> int | None:
        """Persist market snapshot to repository if configured.

        Args:
            market: Market data from Kalshi API
            city_code: City code for the market

        Returns:
            Snapshot ID if saved, None if repositories not configured
        """
        if not self.market_repo:
            return None

        try:
            from src.shared.db.repositories.market import MarketSnapshotCreate

            snapshot_data = MarketSnapshotCreate(
                ticker=market.ticker,
                city_code=city_code,
                event_ticker=market.event_ticker,
                yes_bid=market.yes_bid,
                yes_ask=market.yes_ask,
                volume=market.volume or 0,
                open_interest=market.open_interest or 0,
                status=market.status or "open",
                strike_price=market.strike_price,
            )

            saved = self.market_repo.save_snapshot(snapshot_data)
            logger.debug(
                "market_persisted",
                ticker=market.ticker,
                snapshot_id=saved.id,
            )
            return saved.id
        except Exception as e:
            logger.warning(
                "market_persistence_failed",
                ticker=market.ticker,
                error=str(e),
            )
            return None

    def _persist_signal(
        self,
        signal: Signal,
        market: Market,
        city_code: str,
        weather_snapshot_id: int | None = None,
        market_snapshot_id: int | None = None,
    ) -> int | None:
        """Persist trading signal to repository if configured.

        Args:
            signal: Generated trading signal
            market: Market the signal applies to
            city_code: City code
            weather_snapshot_id: ID of related weather snapshot
            market_snapshot_id: ID of related market snapshot

        Returns:
            Signal ID if saved, None if repositories not configured
        """
        if not self.signal_repo:
            return None

        try:
            from src.shared.db.repositories.signal import SignalCreate

            signal_data = SignalCreate(
                ticker=market.ticker,
                city_code=city_code,
                strategy_name=self.strategy.name,
                side=signal.side,
                decision=signal.decision,
                p_yes=signal.p_yes,
                uncertainty=signal.uncertainty,
                edge=signal.edge,
                max_price=signal.max_price,
                weather_snapshot_id=weather_snapshot_id,
                market_snapshot_id=market_snapshot_id,
                trading_mode=self.trading_mode.value,
            )

            saved = self.signal_repo.save_signal(signal_data)
            logger.debug(
                "signal_persisted",
                ticker=market.ticker,
                signal_id=saved.id,
                decision=signal.decision,
            )
            return saved.id
        except Exception as e:
            logger.warning(
                "signal_persistence_failed",
                ticker=market.ticker,
                error=str(e),
            )
            return None

    def _submit_order(
        self,
        signal: Signal,
        city_config: CityConfig,
        market: Market,
        quantity: int,
    ) -> dict[str, Any] | None:
        """Submit order based on trading mode.

        Args:
            signal: Trading signal
            city_config: City configuration
            market: Market to trade
            quantity: Trade quantity

        Returns:
            Order dictionary if submitted, None otherwise
        """
        # Generate intent key for idempotency
        event_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        limit_price = int(signal.max_price or 50)

        # Extract market_id from ticker or use hash if not available
        # Market ID is typically embedded in the ticker or we can use a hash
        market_id = hash(market.ticker) % 1000000  # Use ticker hash as ID

        # Check for existing order with same intent
        order = self.oms.submit_order(
            signal=signal,
            city_code=city_config.code,
            market_id=market_id,
            event_date=event_date,
            quantity=quantity,
            limit_price=float(limit_price),
        )

        # SHADOW mode - no actual API call
        if self.trading_mode == TradingMode.SHADOW:
            logger.info(
                "shadow_mode_simulated_order",
                ticker=market.ticker,
                side=signal.side,
                quantity=quantity,
                limit_price=limit_price,
                intent_key=order["intent_key"],
            )
            # Simulate fill
            self.oms.update_order_status(
                order["intent_key"],
                OrderState.FILLED,
            )
            return order

        # LIVE mode requires explicit confirmation
        if self.trading_mode == TradingMode.LIVE and not self._live_mode_confirmed:
            logger.error(
                "live_mode_not_confirmed",
                ticker=market.ticker,
                message="LIVE mode requires explicit confirmation via confirm_live_mode()",
            )
            self.oms.update_order_status(
                order["intent_key"],
                OrderState.REJECTED,
                status_message="LIVE mode not confirmed",
            )
            return order

        # DEMO and LIVE modes - submit to Kalshi API
        if self.kalshi_client:
            try:
                result = self.kalshi_client.create_order(
                    ticker=market.ticker,
                    side=signal.side or "yes",
                    action="buy",
                    count=quantity,
                    yes_price=limit_price if signal.side == "yes" else None,
                    no_price=limit_price if signal.side == "no" else None,
                    client_order_id=order["intent_key"],
                )

                # Update OMS with Kalshi order ID
                self.oms.update_order_status(
                    order["intent_key"],
                    OrderState.SUBMITTED,
                    kalshi_order_id=result.get("order_id"),
                )

                logger.info(
                    "order_submitted_to_kalshi",
                    ticker=market.ticker,
                    kalshi_order_id=result.get("order_id"),
                    trading_mode=self.trading_mode.value,
                )

                return order

            except Exception as e:
                # Track rejection for circuit breaker
                import time
                self.circuit_breaker.track_order_rejects(time.time())

                self.oms.update_order_status(
                    order["intent_key"],
                    OrderState.REJECTED,
                )

                logger.error(
                    "kalshi_order_submission_failed",
                    ticker=market.ticker,
                    error=str(e),
                )
                raise

        return order


@dataclass
class MultiCityRunResult:
    """Result of a multi-city trading run.

    Aggregates results from all cities in a single trading session.
    """

    started_at: datetime
    completed_at: datetime
    city_results: dict[str, TradingCycleResult]
    total_weather_fetched: int = 0
    total_markets_fetched: int = 0
    total_signals_generated: int = 0
    total_orders_submitted: int = 0
    cities_succeeded: int = 0
    cities_failed: int = 0

    @property
    def success(self) -> bool:
        """Check if run completed with at least some success."""
        return self.cities_succeeded > 0

    @property
    def duration_seconds(self) -> float:
        """Get total run duration in seconds."""
        return (self.completed_at - self.started_at).total_seconds()


class MultiCityOrchestrator:
    """Orchestrates trading across multiple cities.

    Handles parallel weather fetching, sequential trading cycles,
    and aggregate risk management across all cities.
    """

    def __init__(
        self,
        trading_loop: TradingLoop | None = None,
        city_codes: list[str] | None = None,
        max_parallel_weather: int = 5,
        trading_mode: TradingMode | None = None,
    ) -> None:
        """Initialize multi-city orchestrator.

        Args:
            trading_loop: Trading loop instance (created if not provided)
            city_codes: List of city codes to trade (all cities if not provided)
            max_parallel_weather: Max concurrent weather fetches
            trading_mode: Trading mode override
        """
        self.trading_mode = trading_mode or get_settings().trading_mode
        self.trading_loop = trading_loop or TradingLoop(trading_mode=self.trading_mode)
        self.max_parallel_weather = max_parallel_weather

        # Get city codes from config if not provided
        if city_codes:
            self.city_codes = city_codes
        else:
            self.city_codes = list(city_loader.get_all_cities().keys())

        logger.info(
            "multi_city_orchestrator_initialized",
            city_count=len(self.city_codes),
            trading_mode=self.trading_mode.value,
            max_parallel_weather=max_parallel_weather,
        )

    def prefetch_weather(self) -> dict[str, bool]:
        """Prefetch weather data for all cities in parallel.

        Uses thread pool for concurrent weather fetching.

        Returns:
            Dictionary mapping city codes to success status
        """
        import concurrent.futures

        results: dict[str, bool] = {}

        logger.info(
            "prefetch_weather_started",
            city_count=len(self.city_codes),
            max_parallel=self.max_parallel_weather,
        )

        def fetch_city_weather(city_code: str) -> tuple[str, bool]:
            """Fetch weather for a single city."""
            try:
                self.trading_loop.weather_cache.get_weather(city_code, force_refresh=True)
                return (city_code, True)
            except Exception as e:
                logger.warning(
                    "prefetch_weather_failed",
                    city_code=city_code,
                    error=str(e),
                )
                return (city_code, False)

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_parallel_weather
        ) as executor:
            futures = {
                executor.submit(fetch_city_weather, city): city
                for city in self.city_codes
            }

            for future in concurrent.futures.as_completed(futures):
                city_code, success = future.result()
                results[city_code] = success

        success_count = sum(1 for v in results.values() if v)
        logger.info(
            "prefetch_weather_completed",
            total=len(results),
            success=success_count,
            failed=len(results) - success_count,
        )

        return results

    def run_all_cities(
        self,
        quantity: int = 100,
        prefetch_weather: bool = True,
    ) -> MultiCityRunResult:
        """Run trading cycle for all configured cities.

        Args:
            quantity: Default trade quantity per signal
            prefetch_weather: Whether to prefetch weather in parallel first

        Returns:
            MultiCityRunResult with aggregated statistics
        """
        started_at = datetime.now(timezone.utc)
        city_results: dict[str, TradingCycleResult] = {}

        logger.info(
            "multi_city_run_started",
            city_count=len(self.city_codes),
            trading_mode=self.trading_mode.value,
            prefetch_weather=prefetch_weather,
        )

        # Step 1: Prefetch weather for all cities in parallel
        if prefetch_weather:
            self.prefetch_weather()

        # Step 2: Check aggregate risk before any trades
        # This ensures we don't exceed total portfolio risk
        if not self._check_aggregate_risk():
            logger.warning(
                "multi_city_run_blocked_aggregate_risk",
                reason="Aggregate portfolio risk exceeded",
            )
            return MultiCityRunResult(
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                city_results={},
                cities_failed=len(self.city_codes),
            )

        # Step 3: Run trading cycle for each city sequentially
        # (Market API calls and order submission must be sequential)
        for city_code in self.city_codes:
            try:
                result = self.trading_loop.run_cycle(city_code, quantity)
                city_results[city_code] = result

                logger.debug(
                    "city_cycle_completed",
                    city_code=city_code,
                    success=result.success,
                    orders=result.orders_submitted,
                )
            except Exception as e:
                logger.error(
                    "city_cycle_error",
                    city_code=city_code,
                    error=str(e),
                )
                # Create error result for this city
                city_results[city_code] = TradingCycleResult(
                    city_code=city_code,
                    started_at=datetime.now(timezone.utc),
                    completed_at=datetime.now(timezone.utc),
                    weather_fetched=False,
                    markets_fetched=0,
                    signals_generated=0,
                    gates_passed=0,
                    orders_submitted=0,
                    errors=[str(e)],
                )

        completed_at = datetime.now(timezone.utc)

        # Aggregate statistics
        total_weather = sum(1 for r in city_results.values() if r.weather_fetched)
        total_markets = sum(r.markets_fetched for r in city_results.values())
        total_signals = sum(r.signals_generated for r in city_results.values())
        total_orders = sum(r.orders_submitted for r in city_results.values())
        cities_ok = sum(1 for r in city_results.values() if r.success)
        cities_fail = len(city_results) - cities_ok

        result = MultiCityRunResult(
            started_at=started_at,
            completed_at=completed_at,
            city_results=city_results,
            total_weather_fetched=total_weather,
            total_markets_fetched=total_markets,
            total_signals_generated=total_signals,
            total_orders_submitted=total_orders,
            cities_succeeded=cities_ok,
            cities_failed=cities_fail,
        )

        logger.info(
            "multi_city_run_completed",
            duration_seconds=result.duration_seconds,
            cities_succeeded=cities_ok,
            cities_failed=cities_fail,
            total_weather=total_weather,
            total_markets=total_markets,
            total_signals=total_signals,
            total_orders=total_orders,
        )

        return result

    def _check_aggregate_risk(self) -> bool:
        """Check aggregate risk across all cities.

        Returns:
            True if within risk limits, False otherwise
        """
        # Get all pending orders from OMS
        pending_orders = self.trading_loop.oms.get_orders_by_status("pending")
        resting_orders = self.trading_loop.oms.get_orders_by_status("resting")

        all_open_orders = pending_orders + resting_orders

        # Calculate total exposure
        total_exposure = sum(
            order.get("quantity", 0) * order.get("limit_price", 0) / 100.0
            for order in all_open_orders
        )

        # Check against circuit breaker
        if self.trading_loop.circuit_breaker.is_paused:
            logger.warning(
                "aggregate_risk_circuit_breaker_paused",
                reason=self.trading_loop.circuit_breaker.pause_reason,
            )
            return False

        # Check total exposure limit (configurable, default $50,000)
        max_total_exposure = 50000.0
        if total_exposure > max_total_exposure:
            logger.warning(
                "aggregate_risk_exposure_exceeded",
                current_exposure=total_exposure,
                max_exposure=max_total_exposure,
            )
            return False

        logger.debug(
            "aggregate_risk_check_passed",
            current_exposure=total_exposure,
            max_exposure=max_total_exposure,
            open_orders=len(all_open_orders),
        )

        return True

    def get_run_summary(self, result: MultiCityRunResult) -> dict[str, Any]:
        """Generate a summary report for a multi-city run.

        Args:
            result: MultiCityRunResult from run_all_cities

        Returns:
            Summary dictionary for logging/display
        """
        summary: dict[str, Any] = {
            "duration_seconds": result.duration_seconds,
            "cities_total": len(self.city_codes),
            "cities_succeeded": result.cities_succeeded,
            "cities_failed": result.cities_failed,
            "total_weather_fetched": result.total_weather_fetched,
            "total_markets_fetched": result.total_markets_fetched,
            "total_signals_generated": result.total_signals_generated,
            "total_orders_submitted": result.total_orders_submitted,
            "trading_mode": self.trading_mode.value,
            "per_city": {},
        }

        for city_code, city_result in result.city_results.items():
            summary["per_city"][city_code] = {
                "success": city_result.success,
                "duration_seconds": city_result.duration_seconds,
                "markets_fetched": city_result.markets_fetched,
                "signals_generated": city_result.signals_generated,
                "orders_submitted": city_result.orders_submitted,
                "errors": city_result.errors,
            }

        return summary


# Entry point for running as module
if __name__ == "__main__":
    import sys
    import time
    
    logger.info("trading_loop_starting")
    settings = get_settings()
    
    # Initialize trading loop
    try:
        orchestrator = MultiCityOrchestrator(
            city_codes=["NYC", "CHI", "LAX", "MIA", "AUS", "DEN", "PHL", "BOS", "SEA", "SFO"],
            trading_mode=settings.trading_mode,
        )
        logger.info(
            "orchestrator_initialized",
            trading_mode=settings.trading_mode.value,
            cities=len(orchestrator.city_codes),
        )
    except Exception as e:
        logger.error("orchestrator_init_failed", error=str(e))
        sys.exit(1)
    
    # Run continuous trading loop
    while True:
        try:
            result = orchestrator.run_all_cities()
            summary = orchestrator.get_run_summary(result)
            logger.info("trading_cycle_completed", **summary)
            
            # Sleep between cycles (configurable, default 5 minutes)
            cycle_interval = 300  # seconds
            logger.info("sleeping_until_next_cycle", seconds=cycle_interval)
            time.sleep(cycle_interval)
            
        except KeyboardInterrupt:
            logger.info("trading_loop_interrupted")
            break
        except Exception as e:
            logger.error("trading_cycle_error", error=str(e))
            # Sleep on error to avoid tight loop
            time.sleep(60)
