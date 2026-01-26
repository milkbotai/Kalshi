"""Order Management System (OMS) for trade execution.

Manages order lifecycle with idempotency, state machine, and duplicate prevention.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any

from src.shared.config.logging import get_logger
from src.trader.strategy import Signal

logger = get_logger(__name__)


class OrderState:
    """Order state machine states."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    RESTING = "resting"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    CLOSED = "closed"


class OrderManagementSystem:
    """Order Management System for trade execution.

    Handles order creation with idempotency, state transitions,
    and duplicate prevention using intent keys.
    """

    def __init__(self) -> None:
        """Initialize OMS."""
        self._orders: dict[str, dict[str, Any]] = {}  # intent_key -> order
        logger.info("oms_initialized")

    def generate_intent_key(
        self,
        signal: Signal,
        city_code: str,
        market_id: int,
        event_date: str,
    ) -> str:
        """Generate deterministic intent key for idempotency.

        Args:
            signal: Trading signal
            city_code: 3-letter city code
            market_id: Market ID
            event_date: Event date (YYYY-MM-DD)

        Returns:
            Deterministic intent key (hash)

        Example:
            >>> oms = OrderManagementSystem()
            >>> key = oms.generate_intent_key(signal, "NYC", 123, "2026-01-26")
        """
        # Create deterministic string from inputs
        components = [
            city_code,
            str(market_id),
            signal.side or "",
            signal.ticker,
            event_date,
        ]

        intent_string = "|".join(components)

        # Generate hash
        intent_key = hashlib.sha256(intent_string.encode()).hexdigest()[:16]

        logger.debug(
            "intent_key_generated",
            city_code=city_code,
            market_id=market_id,
            ticker=signal.ticker,
            intent_key=intent_key,
        )

        return intent_key

    def submit_order(
        self,
        signal: Signal,
        city_code: str,
        market_id: int,
        event_date: str,
        quantity: int,
        limit_price: float,
    ) -> dict[str, Any]:
        """Submit order with idempotency check.

        Checks for existing order with same intent key before creating new order.

        Args:
            signal: Trading signal
            city_code: 3-letter city code
            market_id: Market ID
            event_date: Event date (YYYY-MM-DD)
            quantity: Number of contracts
            limit_price: Limit price in cents

        Returns:
            Order dictionary (existing or newly created)

        Example:
            >>> oms = OrderManagementSystem()
            >>> order = oms.submit_order(signal, "NYC", 123, "2026-01-26", 100, 45.0)
        """
        # Generate intent key
        intent_key = self.generate_intent_key(signal, city_code, market_id, event_date)

        # Check for existing order with same intent
        if intent_key in self._orders:
            existing_order = self._orders[intent_key]
            logger.info(
                "order_already_exists",
                intent_key=intent_key,
                order_id=existing_order.get("order_id"),
                status=existing_order.get("status"),
                reason="Duplicate intent key, returning existing order",
            )
            return existing_order

        # Create new order
        order = {
            "intent_key": intent_key,
            "order_id": None,  # Will be set when submitted to exchange
            "ticker": signal.ticker,
            "city_code": city_code,
            "market_id": market_id,
            "event_date": event_date,
            "side": signal.side,
            "action": "buy",  # Always buy for now
            "quantity": quantity,
            "limit_price": limit_price,
            "status": OrderState.PENDING,
            "created_at": datetime.now(timezone.utc),
            "submitted_at": None,
            "filled_at": None,
            "cancelled_at": None,
            "filled_quantity": 0,
            "remaining_quantity": quantity,
            "average_fill_price": None,
            "kalshi_order_id": None,
            "signal_p_yes": signal.p_yes,
            "signal_edge": signal.edge,
        }

        # Store order
        self._orders[intent_key] = order

        logger.info(
            "order_created",
            intent_key=intent_key,
            ticker=signal.ticker,
            side=signal.side,
            quantity=quantity,
            limit_price=limit_price,
        )

        return order

    def update_order_status(
        self,
        intent_key: str,
        status: str,
        kalshi_order_id: str | None = None,
        status_message: str | None = None,
    ) -> bool:
        """Update order status and metadata.

        Args:
            intent_key: Order intent key
            status: New status
            kalshi_order_id: Kalshi order ID if available
            status_message: Status message or error details

        Returns:
            True if order updated, False if not found
        """
        if intent_key not in self._orders:
            logger.warning("order_not_found", intent_key=intent_key)
            return False

        order = self._orders[intent_key]
        old_status = order["status"]

        # Update status
        order["status"] = status

        if kalshi_order_id:
            order["kalshi_order_id"] = kalshi_order_id

        # Update timestamps based on status
        if status == OrderState.SUBMITTED and order["submitted_at"] is None:
            order["submitted_at"] = datetime.now(timezone.utc)
        elif status == OrderState.FILLED and order["filled_at"] is None:
            order["filled_at"] = datetime.now(timezone.utc)
        elif status == OrderState.CANCELLED and order["cancelled_at"] is None:
            order["cancelled_at"] = datetime.now(timezone.utc)

        logger.info(
            "order_status_updated",
            intent_key=intent_key,
            old_status=old_status,
            new_status=status,
            kalshi_order_id=kalshi_order_id,
            message=status_message,
        )

        return True

    def get_order_by_intent_key(self, intent_key: str) -> dict[str, Any] | None:
        """Get order by intent key.

        Args:
            intent_key: Order intent key

        Returns:
            Order dictionary or None if not found
        """
        return self._orders.get(intent_key)

    def get_all_orders(self) -> list[dict[str, Any]]:
        """Get all orders.

        Returns:
            List of all order dictionaries
        """
        return list(self._orders.values())

    def get_orders_by_status(self, status: str) -> list[dict[str, Any]]:
        """Get orders filtered by status.

        Args:
            status: Order status to filter by

        Returns:
            List of orders with matching status
        """
        return [order for order in self._orders.values() if order["status"] == status]

    def reconcile_fills(
        self,
        kalshi_fills: list[dict[str, Any]],
        since_timestamp: datetime | None = None,
    ) -> dict[str, Any]:
        """Reconcile Kalshi fills with local orders.

        Matches fills to local orders by client_order_id (intent_key),
        updates order status, and detects orphaned fills.

        Args:
            kalshi_fills: List of fill dictionaries from Kalshi API
            since_timestamp: Only process fills after this timestamp

        Returns:
            Reconciliation summary with matched, orphaned, and updated counts

        Example:
            >>> oms = OrderManagementSystem()
            >>> fills = [{"order_id": "order_123", "count": 10, "price": 45}]
            >>> summary = oms.reconcile_fills(fills)
        """
        matched_count = 0
        orphaned_count = 0
        updated_orders = []
        orphaned_fills = []

        for fill in kalshi_fills:
            # Extract fill details
            kalshi_order_id = fill.get("order_id")
            filled_qty = fill.get("count", 0)
            fill_price = fill.get("yes_price") or fill.get("no_price", 0)
            fill_time_str = fill.get("created_time")

            # Parse fill timestamp
            if fill_time_str:
                try:
                    fill_time = datetime.fromisoformat(fill_time_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    fill_time = datetime.now(timezone.utc)
            else:
                fill_time = datetime.now(timezone.utc)

            # Skip if before since_timestamp
            if since_timestamp and fill_time < since_timestamp:
                continue

            # Find matching local order by kalshi_order_id
            matching_order = None
            for order in self._orders.values():
                if order.get("kalshi_order_id") == kalshi_order_id:
                    matching_order = order
                    break

            if matching_order:
                # Update order with fill information
                intent_key = matching_order["intent_key"]

                # Update filled quantity
                matching_order["filled_quantity"] += filled_qty
                matching_order["remaining_quantity"] = (
                    matching_order["quantity"] - matching_order["filled_quantity"]
                )

                # Update average fill price
                if matching_order["average_fill_price"] is None:
                    matching_order["average_fill_price"] = fill_price
                else:
                    # Weighted average
                    total_filled = matching_order["filled_quantity"]
                    prev_filled = total_filled - filled_qty
                    prev_avg = matching_order["average_fill_price"]

                    matching_order["average_fill_price"] = (
                        prev_avg * prev_filled + fill_price * filled_qty
                    ) / total_filled

                # Update status
                if matching_order["filled_quantity"] >= matching_order["quantity"]:
                    matching_order["status"] = OrderState.FILLED
                    matching_order["filled_at"] = fill_time
                else:
                    matching_order["status"] = OrderState.PARTIALLY_FILLED

                matched_count += 1
                updated_orders.append(intent_key)

                logger.info(
                    "fill_matched",
                    intent_key=intent_key,
                    kalshi_order_id=kalshi_order_id,
                    filled_qty=filled_qty,
                    fill_price=fill_price,
                    total_filled=matching_order["filled_quantity"],
                    status=matching_order["status"],
                )
            else:
                # Orphaned fill - no matching local order
                orphaned_count += 1
                orphaned_fills.append(fill)

                logger.warning(
                    "orphaned_fill_detected",
                    kalshi_order_id=kalshi_order_id,
                    filled_qty=filled_qty,
                    fill_price=fill_price,
                    reason="No matching local order found",
                )

        summary = {
            "total_fills": len(kalshi_fills),
            "matched_count": matched_count,
            "orphaned_count": orphaned_count,
            "updated_orders": updated_orders,
            "orphaned_fills": orphaned_fills,
        }

        logger.info(
            "reconciliation_complete",
            total_fills=len(kalshi_fills),
            matched=matched_count,
            orphaned=orphaned_count,
        )

        return summary
