"""Risk calculator for position limits and exposure management.

Calculates open risk, enforces city and cluster exposure limits,
and validates trade sizes against configured caps.
"""

from typing import Any

from src.shared.api.response_models import Market
from src.shared.config.logging import get_logger
from src.shared.config.settings import get_settings
from src.shared.constants import MAX_POSITION_SIZE

logger = get_logger(__name__)


class RiskCalculator:
    """Calculates and enforces risk limits for trading.
    
    Manages position limits, city exposure, cluster exposure,
    and per-trade size constraints.
    """

    def __init__(
        self,
        max_city_exposure_pct: float = 0.03,
        max_cluster_exposure_pct: float = 0.05,
        max_trade_risk_pct: float = 0.02,
        bankroll: float = 5000.0,
    ) -> None:
        """Initialize risk calculator.
        
        Args:
            max_city_exposure_pct: Maximum exposure per city as % of bankroll
            max_cluster_exposure_pct: Maximum exposure per cluster as % of bankroll
            max_trade_risk_pct: Maximum risk per trade as % of bankroll
            bankroll: Total bankroll in dollars
        """
        self.max_city_exposure_pct = max_city_exposure_pct
        self.max_cluster_exposure_pct = max_cluster_exposure_pct
        self.max_trade_risk_pct = max_trade_risk_pct
        self.bankroll = bankroll
        
        # Calculate dollar limits
        self.max_city_exposure = bankroll * max_city_exposure_pct
        self.max_cluster_exposure = bankroll * max_cluster_exposure_pct
        self.max_trade_risk = bankroll * max_trade_risk_pct
        
        logger.info(
            "risk_calculator_initialized",
            bankroll=bankroll,
            max_city_exposure=self.max_city_exposure,
            max_cluster_exposure=self.max_cluster_exposure,
            max_trade_risk=self.max_trade_risk,
        )

    def calculate_open_risk(self, positions: list[dict[str, Any]]) -> float:
        """Calculate total at-risk capital from open positions.
        
        Args:
            positions: List of position dictionaries with ticker, quantity, entry_price
            
        Returns:
            Total at-risk capital in dollars
            
        Example:
            >>> calc = RiskCalculator()
            >>> positions = [
            ...     {"ticker": "TEST-01", "quantity": 100, "entry_price": 45.0},
            ...     {"ticker": "TEST-02", "quantity": 50, "entry_price": 60.0},
            ... ]
            >>> risk = calc.calculate_open_risk(positions)
            >>> # risk = (100 * 45 + 50 * 60) / 100 = 75.0
        """
        total_risk = 0.0
        
        for position in positions:
            quantity = position.get("quantity", 0)
            entry_price = position.get("entry_price", 0.0)
            
            # Risk = quantity * entry_price (in cents) / 100 (convert to dollars)
            position_risk = (quantity * entry_price) / 100.0
            total_risk += position_risk
        
        logger.debug(
            "open_risk_calculated",
            num_positions=len(positions),
            total_risk=total_risk,
        )
        
        return total_risk

    def check_city_exposure(
        self,
        city_code: str,
        new_trade_risk: float,
        existing_positions: list[dict[str, Any]],
    ) -> bool:
        """Check if new trade would exceed city exposure limit.
        
        Args:
            city_code: 3-letter city code
            new_trade_risk: Risk of new trade in dollars
            existing_positions: List of existing positions with city_code
            
        Returns:
            True if trade allowed, False if would exceed limit
            
        Example:
            >>> calc = RiskCalculator()
            >>> positions = [{"city_code": "NYC", "quantity": 100, "entry_price": 45.0}]
            >>> allowed = calc.check_city_exposure("NYC", 50.0, positions)
        """
        # Calculate current city exposure
        city_positions = [p for p in existing_positions if p.get("city_code") == city_code]
        current_exposure = self.calculate_open_risk(city_positions)
        
        # Check if new trade would exceed limit
        total_exposure = current_exposure + new_trade_risk
        
        if total_exposure > self.max_city_exposure:
            logger.warning(
                "city_exposure_limit_exceeded",
                city_code=city_code,
                current_exposure=current_exposure,
                new_trade_risk=new_trade_risk,
                total_exposure=total_exposure,
                max_exposure=self.max_city_exposure,
                reason=f"City exposure ${total_exposure:.2f} exceeds limit ${self.max_city_exposure:.2f}",
            )
            return False
        
        logger.debug(
            "city_exposure_check_passed",
            city_code=city_code,
            total_exposure=total_exposure,
            max_exposure=self.max_city_exposure,
        )
        
        return True

    def check_cluster_exposure(
        self,
        cluster: str,
        new_trade_risk: float,
        existing_positions: list[dict[str, Any]],
    ) -> bool:
        """Check if new trade would exceed cluster exposure limit.
        
        Args:
            cluster: Cluster name (NE, SE, Midwest, Mountain, West)
            new_trade_risk: Risk of new trade in dollars
            existing_positions: List of existing positions with cluster
            
        Returns:
            True if trade allowed, False if would exceed limit
            
        Example:
            >>> calc = RiskCalculator()
            >>> positions = [{"cluster": "NE", "quantity": 100, "entry_price": 45.0}]
            >>> allowed = calc.check_cluster_exposure("NE", 100.0, positions)
        """
        # Calculate current cluster exposure
        cluster_positions = [p for p in existing_positions if p.get("cluster") == cluster]
        current_exposure = self.calculate_open_risk(cluster_positions)
        
        # Check if new trade would exceed limit
        total_exposure = current_exposure + new_trade_risk
        
        if total_exposure > self.max_cluster_exposure:
            logger.warning(
                "cluster_exposure_limit_exceeded",
                cluster=cluster,
                current_exposure=current_exposure,
                new_trade_risk=new_trade_risk,
                total_exposure=total_exposure,
                max_exposure=self.max_cluster_exposure,
                reason=f"Cluster exposure ${total_exposure:.2f} exceeds limit ${self.max_cluster_exposure:.2f}",
            )
            return False
        
        logger.debug(
            "cluster_exposure_check_passed",
            cluster=cluster,
            total_exposure=total_exposure,
            max_exposure=self.max_cluster_exposure,
        )
        
        return True

    def check_trade_size(self, trade_risk: float, quantity: int) -> bool:
        """Check if trade size is within limits.
        
        Args:
            trade_risk: Trade risk in dollars
            quantity: Number of contracts
            
        Returns:
            True if trade size allowed, False if exceeds limits
            
        Example:
            >>> calc = RiskCalculator()
            >>> allowed = calc.check_trade_size(trade_risk=50.0, quantity=100)
        """
        # Check per-trade risk limit
        if trade_risk > self.max_trade_risk:
            logger.warning(
                "trade_risk_limit_exceeded",
                trade_risk=trade_risk,
                max_trade_risk=self.max_trade_risk,
                reason=f"Trade risk ${trade_risk:.2f} exceeds limit ${self.max_trade_risk:.2f}",
            )
            return False
        
        # Check maximum position size
        if quantity > MAX_POSITION_SIZE:
            logger.warning(
                "position_size_limit_exceeded",
                quantity=quantity,
                max_position_size=MAX_POSITION_SIZE,
                reason=f"Quantity {quantity} exceeds max {MAX_POSITION_SIZE}",
            )
            return False
        
        logger.debug(
            "trade_size_check_passed",
            trade_risk=trade_risk,
            quantity=quantity,
        )
        
        return True


class CircuitBreaker:
    """Manages circuit breakers for trading pauses.
    
    Tracks daily P&L, order rejects, and triggers trading pauses
    when limits are exceeded.
    """

    def __init__(
        self,
        max_daily_loss: float = 250.0,
        max_rejects_window: int = 5,
        reject_window_minutes: int = 15,
    ) -> None:
        """Initialize circuit breaker.
        
        Args:
            max_daily_loss: Maximum daily loss in dollars before pause
            max_rejects_window: Maximum order rejects in time window
            reject_window_minutes: Time window for reject tracking in minutes
        """
        self.max_daily_loss = max_daily_loss
        self.max_rejects_window = max_rejects_window
        self.reject_window_minutes = reject_window_minutes
        
        self._paused = False
        self._pause_reason: str | None = None
        self._reject_timestamps: list[float] = []
        
        logger.info(
            "circuit_breaker_initialized",
            max_daily_loss=max_daily_loss,
            max_rejects_window=max_rejects_window,
            reject_window_minutes=reject_window_minutes,
        )

    def track_daily_pnl(
        self,
        realized_pnl: float,
        unrealized_pnl: float,
    ) -> float:
        """Calculate total daily P&L.
        
        Args:
            realized_pnl: Realized P&L from closed positions in dollars
            unrealized_pnl: Unrealized P&L from open positions in dollars
            
        Returns:
            Total daily P&L in dollars
            
        Example:
            >>> breaker = CircuitBreaker()
            >>> pnl = breaker.track_daily_pnl(realized_pnl=100.0, unrealized_pnl=-50.0)
            >>> # pnl = 50.0
        """
        total_pnl = realized_pnl + unrealized_pnl
        
        logger.debug(
            "daily_pnl_tracked",
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
        )
        
        return total_pnl

    def check_daily_loss_limit(
        self,
        realized_pnl: float,
        unrealized_pnl: float,
    ) -> bool:
        """Check if daily loss limit exceeded and trigger pause if needed.
        
        Args:
            realized_pnl: Realized P&L in dollars
            unrealized_pnl: Unrealized P&L in dollars
            
        Returns:
            True if trading allowed, False if paused due to loss limit
            
        Example:
            >>> breaker = CircuitBreaker(max_daily_loss=250.0)
            >>> allowed = breaker.check_daily_loss_limit(
            ...     realized_pnl=-200.0,
            ...     unrealized_pnl=-100.0,
            ... )
            >>> # allowed = False (total loss = -300.0 > -250.0)
        """
        total_pnl = self.track_daily_pnl(realized_pnl, unrealized_pnl)
        
        # Check if loss exceeds limit (negative P&L)
        if total_pnl < -self.max_daily_loss:
            if not self._paused:
                self._paused = True
                self._pause_reason = f"Daily loss ${abs(total_pnl):.2f} exceeds limit ${self.max_daily_loss:.2f}"
                
                logger.critical(
                    "daily_loss_limit_exceeded_trading_paused",
                    total_pnl=total_pnl,
                    max_daily_loss=self.max_daily_loss,
                    reason=self._pause_reason,
                )
            
            return False
        
        logger.debug(
            "daily_loss_check_passed",
            total_pnl=total_pnl,
            max_daily_loss=self.max_daily_loss,
        )
        
        return True

    def track_order_rejects(self, reject_timestamp: float) -> int:
        """Track order rejection and count recent rejects.
        
        Args:
            reject_timestamp: Unix timestamp of rejection
            
        Returns:
            Number of rejects in sliding window
            
        Example:
            >>> breaker = CircuitBreaker()
            >>> import time
            >>> count = breaker.track_order_rejects(time.time())
        """
        import time
        
        # Add new reject
        self._reject_timestamps.append(reject_timestamp)
        
        # Remove rejects outside window
        window_start = time.time() - (self.reject_window_minutes * 60)
        self._reject_timestamps = [
            ts for ts in self._reject_timestamps if ts >= window_start
        ]
        
        reject_count = len(self._reject_timestamps)
        
        logger.debug(
            "order_rejects_tracked",
            reject_count=reject_count,
            window_minutes=self.reject_window_minutes,
        )
        
        # Check if threshold exceeded
        if reject_count >= self.max_rejects_window:
            if not self._paused:
                self._paused = True
                self._pause_reason = (
                    f"{reject_count} order rejects in {self.reject_window_minutes} minutes"
                )
                
                logger.critical(
                    "reject_threshold_exceeded_trading_paused",
                    reject_count=reject_count,
                    max_rejects=self.max_rejects_window,
                    window_minutes=self.reject_window_minutes,
                    reason=self._pause_reason,
                )
        
        return reject_count

    @property
    def is_paused(self) -> bool:
        """Check if trading is currently paused.
        
        Returns:
            True if trading is paused
        """
        return self._paused

    @property
    def pause_reason(self) -> str | None:
        """Get reason for trading pause.
        
        Returns:
            Pause reason string, or None if not paused
        """
        return self._pause_reason

    def reset_pause(self) -> None:
        """Reset pause state (manual intervention required).
        
        Should only be called after reviewing and resolving the issue
        that triggered the pause.
        """
        if self._paused:
            logger.warning(
                "circuit_breaker_reset",
                previous_reason=self._pause_reason,
            )
        
        self._paused = False
        self._pause_reason = None
        self._reject_timestamps = []
