"""Execution gate checks for trade validation.

Validates market conditions before allowing trade execution including
spread, liquidity, and edge requirements.
"""

from src.shared.api.response_models import Market
from src.shared.config.logging import get_logger
from src.shared.config.settings import get_settings
from src.trader.strategy import Signal

logger = get_logger(__name__)


def check_spread(market: Market, max_spread_cents: int = 3) -> bool:
    """Check if market spread is acceptable.

    Args:
        market: Market to check
        max_spread_cents: Maximum acceptable spread in cents

    Returns:
        True if spread <= max_spread_cents

    Example:
        >>> market = Market(ticker="TEST", yes_bid=45, yes_ask=48, ...)
        >>> check_spread(market, max_spread_cents=3)
        True
    """
    if market.spread_cents is None:
        logger.warning(
            "spread_check_failed_no_pricing",
            ticker=market.ticker,
            reason="No bid/ask pricing available",
        )
        return False

    if market.spread_cents > max_spread_cents:
        logger.info(
            "spread_check_failed",
            ticker=market.ticker,
            spread_cents=market.spread_cents,
            max_spread_cents=max_spread_cents,
            reason=f"Spread {market.spread_cents}¢ exceeds max {max_spread_cents}¢",
        )
        return False

    logger.debug(
        "spread_check_passed",
        ticker=market.ticker,
        spread_cents=market.spread_cents,
    )
    return True


def check_liquidity(
    market: Market,
    quantity: int,
    min_liquidity_multiple: float = 5.0,
) -> bool:
    """Check if market has sufficient liquidity.

    Args:
        market: Market to check
        quantity: Desired trade quantity
        min_liquidity_multiple: Minimum liquidity as multiple of quantity

    Returns:
        True if total liquidity >= quantity * min_liquidity_multiple

    Example:
        >>> market = Market(ticker="TEST", volume=1000, open_interest=5000, ...)
        >>> check_liquidity(market, quantity=100, min_liquidity_multiple=5.0)
        True  # 6000 >= 100 * 5
    """
    total_liquidity = market.volume + market.open_interest
    required_liquidity = quantity * min_liquidity_multiple

    if total_liquidity < required_liquidity:
        logger.info(
            "liquidity_check_failed",
            ticker=market.ticker,
            total_liquidity=total_liquidity,
            required_liquidity=required_liquidity,
            quantity=quantity,
            reason=f"Liquidity {total_liquidity} below required {required_liquidity}",
        )
        return False

    logger.debug(
        "liquidity_check_passed",
        ticker=market.ticker,
        total_liquidity=total_liquidity,
        quantity=quantity,
    )
    return True


def check_edge(
    signal: Signal,
    min_edge_cents: float = 0.5,
) -> bool:
    """Check if signal has sufficient edge.

    Args:
        signal: Signal to check
        min_edge_cents: Minimum edge required in cents

    Returns:
        True if edge >= min_edge_cents

    Example:
        >>> signal = Signal(ticker="TEST", p_yes=0.6, edge=5.0, ...)
        >>> check_edge(signal, min_edge_cents=0.5)
        True
    """
    if signal.edge < min_edge_cents:
        logger.info(
            "edge_check_failed",
            ticker=signal.ticker,
            edge=signal.edge,
            min_edge_cents=min_edge_cents,
            reason=f"Edge {signal.edge:.2f}¢ below minimum {min_edge_cents}¢",
        )
        return False

    logger.debug(
        "edge_check_passed",
        ticker=signal.ticker,
        edge=signal.edge,
    )
    return True


def check_all_gates(
    signal: Signal,
    market: Market,
    quantity: int,
    max_spread_cents: int | None = None,
    min_liquidity_multiple: float | None = None,
    min_edge_cents: float | None = None,
) -> tuple[bool, list[str]]:
    """Check all execution gates.

    Gate defaults are loaded from settings (spread_max_cents, liquidity_min,
    min_edge_after_costs) unless overridden by explicit arguments.

    Args:
        signal: Trading signal
        market: Market to trade
        quantity: Desired trade quantity
        max_spread_cents: Maximum acceptable spread (default from settings)
        min_liquidity_multiple: Minimum liquidity multiple (default 3.0)
        min_edge_cents: Minimum edge required in cents (default from settings)

    Returns:
        Tuple of (all_passed, failed_reasons)

    Example:
        >>> passed, reasons = check_all_gates(signal, market, quantity=100)
        >>> if passed:
        ...     # Execute trade
    """
    settings = get_settings()
    if max_spread_cents is None:
        max_spread_cents = settings.spread_max_cents
    if min_liquidity_multiple is None:
        min_liquidity_multiple = 3.0
    if min_edge_cents is None:
        min_edge_cents = settings.min_edge_after_costs * 100  # Convert fraction to cents
    failed_reasons = []

    if not check_spread(market, max_spread_cents):
        failed_reasons.append("spread_too_wide")

    if not check_liquidity(market, quantity, min_liquidity_multiple):
        failed_reasons.append("insufficient_liquidity")

    if not check_edge(signal, min_edge_cents):
        failed_reasons.append("insufficient_edge")

    all_passed = len(failed_reasons) == 0

    if all_passed:
        logger.info("all_gates_passed", ticker=signal.ticker)
    else:
        logger.warning(
            "gates_failed",
            ticker=signal.ticker,
            failed_reasons=failed_reasons,
        )

    return all_passed, failed_reasons
