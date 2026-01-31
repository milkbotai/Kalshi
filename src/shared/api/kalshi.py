"""Kalshi API client for market data and trading.

Handles authentication, market discovery, order placement, and position tracking.
Implements rate limiting and retry logic per Kalshi API guidelines.

Authentication: Uses RSA key-based authentication per Kalshi API v2.
See: https://docs.kalshi.com/sdks/python/quickstart
"""

import base64
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.shared.api.response_models import Market, Orderbook, OrderbookLevel
from src.shared.config.logging import get_logger
from src.shared.constants import KALSHI_RATE_LIMIT_PER_SECOND

logger = get_logger(__name__)


class KalshiClient:
    """Client for Kalshi trading API.

    Handles authentication, market data retrieval, order placement,
    and position tracking with automatic retries and rate limiting.

    Authentication: Uses RSA key-based signatures per Kalshi API v2.
    """

    def __init__(
        self,
        api_key_id: str | None = None,
        private_key_path: str | None = None,
        private_key_pem: str | None = None,
        base_url: str = "https://demo-api.kalshi.co/trade-api/v2",
        # Legacy parameters (deprecated)
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        """Initialize Kalshi API client with RSA key authentication.

        Args:
            api_key_id: Kalshi API key ID (UUID format)
            private_key_path: Path to RSA private key file (.pem)
            private_key_pem: RSA private key as PEM string (alternative to path)
            base_url: API base URL (demo or production)
            api_key: Deprecated - use api_key_id
            api_secret: Deprecated - not used with RSA auth
        """
        self.api_key_id = api_key_id or api_key
        self.base_url = base_url.rstrip("/")
        self._private_key: rsa.RSAPrivateKey | None = None
        self._last_request_time = 0.0

        # Load private key
        if private_key_path:
            self._load_private_key_from_file(private_key_path)
        elif private_key_pem:
            self._load_private_key_from_pem(private_key_pem)

        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        logger.info(
            "kalshi_client_initialized",
            base_url=base_url,
            has_key=bool(self.api_key_id),
            has_private_key=bool(self._private_key),
        )

    def _load_private_key_from_file(self, path: str) -> None:
        """Load RSA private key from PEM file."""
        try:
            key_path = Path(path)
            if not key_path.exists():
                logger.error("private_key_file_not_found", path=path)
                return

            pem_data = key_path.read_bytes()
            self._private_key = cast(
                rsa.RSAPrivateKey,
                serialization.load_pem_private_key(pem_data, password=None),
            )
            logger.info("private_key_loaded", path=path)
        except Exception as e:
            logger.error("private_key_load_error", path=path, error=str(e))
            raise

    def _load_private_key_from_pem(self, pem_data: str) -> None:
        """Load RSA private key from PEM string."""
        try:
            self._private_key = cast(
                rsa.RSAPrivateKey,
                serialization.load_pem_private_key(pem_data.encode(), password=None),
            )
            logger.info("private_key_loaded_from_string")
        except Exception as e:
            logger.error("private_key_load_error", error=str(e))
            raise

    def _generate_signature(self, timestamp_ms: int, method: str, path: str) -> str:
        """Generate RSA-PSS signature for Kalshi API request.

        Per Kalshi docs: sign(timestamp + method + path) with RSA-PSS SHA256.
        Path must include full API path (e.g., /trade-api/v2/portfolio/balance).
        """
        if not self._private_key:
            raise ValueError("Private key not loaded - cannot sign request")

        # Message format: timestamp_ms + METHOD + path (strip query params)
        path_without_query = path.split("?")[0]
        message = f"{timestamp_ms}{method}{path_without_query}"
        message_bytes = message.encode("utf-8")

        # Sign with RSA-PSS (as per Kalshi docs)
        signature = self._private_key.sign(
            message_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )

        # Return base64-encoded signature
        return base64.b64encode(signature).decode("utf-8")

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests.

        Kalshi allows up to 10 requests per second.
        """
        elapsed = time.time() - self._last_request_time
        min_interval = 1.0 / KALSHI_RATE_LIMIT_PER_SECOND

        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug("rate_limit_sleep", sleep_seconds=sleep_time)
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def _get_auth_headers(self, method: str, endpoint: str) -> dict[str, str]:
        """Generate authentication headers for Kalshi API request.

        Uses RSA key-based authentication per Kalshi API v2.
        Headers: KALSHI-ACCESS-KEY, KALSHI-ACCESS-TIMESTAMP, KALSHI-ACCESS-SIGNATURE

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: Endpoint path (e.g., /portfolio/balance) - without base URL
        """
        if not self.api_key_id or not self._private_key:
            raise ValueError("API key ID and private key required for authentication")

        # Generate timestamp in milliseconds
        timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        # Build full path for signature (must include /trade-api/v2)
        # base_url is like https://demo-api.kalshi.co/trade-api/v2
        # We need to sign /trade-api/v2/portfolio/balance, not just /portfolio/balance
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        full_path = parsed.path + endpoint  # e.g., /trade-api/v2 + /portfolio/balance

        # Generate signature
        signature = self._generate_signature(timestamp_ms, method, full_path)

        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": str(timestamp_ms),
            "KALSHI-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json",
        }

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make authenticated HTTP request to Kalshi API.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path (without base URL)
            params: Query parameters
            json_data: JSON request body

        Returns:
            JSON response as dictionary

        Raises:
            requests.HTTPError: If request fails after retries
        """
        self._rate_limit()

        url = f"{self.base_url}{endpoint}"

        # Generate auth headers (sign path WITHOUT query params)
        headers = self._get_auth_headers(method.upper(), endpoint)

        logger.debug("kalshi_request", method=method, url=url)

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Regenerate headers on retry (fresh timestamp)
                if attempt > 0:
                    headers = self._get_auth_headers(method.upper(), endpoint)

                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data,
                    timeout=30,
                )
                response.raise_for_status()

                logger.debug("kalshi_request_success", url=url, status=response.status_code)
                return cast(dict[str, Any], response.json())

            except requests.HTTPError as e:
                status_code = e.response.status_code if e.response else None

                # Retry on server errors and rate limiting
                if status_code in [429, 500, 502, 503, 504] and attempt < max_retries - 1:
                    backoff_time = 2**attempt
                    logger.warning(
                        "kalshi_request_retry",
                        url=url,
                        status=status_code,
                        attempt=attempt + 1,
                        backoff_seconds=backoff_time,
                    )
                    time.sleep(backoff_time)
                    continue

                logger.error(
                    "kalshi_request_failed",
                    url=url,
                    status=status_code,
                    error=str(e),
                    response_text=e.response.text[:500] if e.response else None,
                )
                raise

            except requests.RequestException as e:
                logger.error("kalshi_request_error", url=url, error=str(e))
                raise

        raise requests.HTTPError("Max retries exceeded")  # pragma: no cover

    def get_markets(
        self,
        event_ticker: str | None = None,
        series_ticker: str | None = None,
        status: str = "open",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get list of markets.

        Args:
            event_ticker: Filter by event ticker
            series_ticker: Filter by series ticker
            status: Market status (open, closed, settled)
            limit: Maximum number of results

        Returns:
            List of market data dictionaries

        Example:
            >>> client = KalshiClient(key, secret)
            >>> markets = client.get_markets(series_ticker="HIGHNYC")
        """
        params: dict[str, Any] = {
            "status": status,
            "limit": limit,
        }

        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker

        logger.info(
            "fetching_kalshi_markets",
            event_ticker=event_ticker,
            series_ticker=series_ticker,
        )

        data = self._make_request("GET", "/markets", params=params)
        return cast(list[dict[str, Any]], data.get("markets", []))

    def get_market(self, ticker: str) -> dict[str, Any]:
        """Get detailed information for a specific market.

        Args:
            ticker: Market ticker

        Returns:
            Market data dictionary

        Example:
            >>> client = KalshiClient(key, secret)
            >>> market = client.get_market("HIGHNYC-25JAN26")
        """
        logger.info("fetching_kalshi_market", ticker=ticker)

        data = self._make_request("GET", f"/markets/{ticker}")
        return cast(dict[str, Any], data.get("market", {}))

    def get_orderbook(self, ticker: str) -> dict[str, Any]:
        """Get orderbook for a market.

        Args:
            ticker: Market ticker

        Returns:
            Orderbook data with bids and asks

        Example:
            >>> client = KalshiClient(key, secret)
            >>> orderbook = client.get_orderbook("HIGHNYC-25JAN26")
            >>> yes_bid = orderbook["yes"][0]["price"]
        """
        logger.info("fetching_kalshi_orderbook", ticker=ticker)

        data = self._make_request("GET", f"/markets/{ticker}/orderbook")
        return cast(dict[str, Any], data.get("orderbook", {}))

    def create_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int,
        order_type: str = "limit",
        yes_price: int | None = None,
        no_price: int | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new order.

        Args:
            ticker: Market ticker
            side: Order side ("yes" or "no")
            action: Order action ("buy" or "sell")
            count: Number of contracts
            order_type: Order type ("limit" or "market")
            yes_price: Limit price for yes side (in cents)
            no_price: Limit price for no side (in cents)
            client_order_id: Client-provided order ID for idempotency

        Returns:
            Order data dictionary

        Example:
            >>> client = KalshiClient(key, secret)
            >>> order = client.create_order(
            ...     ticker="HIGHNYC-25JAN26",
            ...     side="yes",
            ...     action="buy",
            ...     count=10,
            ...     yes_price=45,
            ... )
        """
        payload: dict[str, Any] = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": order_type,
        }

        if yes_price is not None:
            payload["yes_price"] = yes_price
        if no_price is not None:
            payload["no_price"] = no_price
        if client_order_id is not None:
            payload["client_order_id"] = client_order_id

        logger.info(
            "creating_kalshi_order",
            ticker=ticker,
            side=side,
            action=action,
            count=count,
        )

        data = self._make_request("POST", "/portfolio/orders", json_data=payload)
        return cast(dict[str, Any], data.get("order", {}))

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an existing order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancellation response

        Example:
            >>> client = KalshiClient(key, secret)
            >>> result = client.cancel_order("order_123")
        """
        logger.info("canceling_kalshi_order", order_id=order_id)

        data = self._make_request("DELETE", f"/portfolio/orders/{order_id}")
        return data

    def get_orders(
        self,
        ticker: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get list of orders.

        Args:
            ticker: Filter by market ticker
            status: Filter by order status
            limit: Maximum number of results

        Returns:
            List of order data dictionaries
        """
        params: dict[str, Any] = {"limit": limit}

        if ticker:
            params["ticker"] = ticker
        if status:
            params["status"] = status

        logger.info("fetching_kalshi_orders", ticker=ticker, status=status)

        data = self._make_request("GET", "/portfolio/orders", params=params)
        return cast(list[dict[str, Any]], data.get("orders", []))

    def get_positions(self) -> list[dict[str, Any]]:
        """Get current positions.

        Returns:
            List of position data dictionaries

        Example:
            >>> client = KalshiClient(key, secret)
            >>> positions = client.get_positions()
        """
        logger.info("fetching_kalshi_positions")

        data = self._make_request("GET", "/portfolio/positions")
        return cast(list[dict[str, Any]], data.get("positions", []))

    def get_fills(
        self,
        ticker: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get fill history.

        Args:
            ticker: Filter by market ticker
            min_ts: Minimum timestamp (Unix milliseconds)
            max_ts: Maximum timestamp (Unix milliseconds)
            limit: Maximum number of results

        Returns:
            List of fill data dictionaries

        Example:
            >>> client = KalshiClient(key, secret)
            >>> fills = client.get_fills(ticker="HIGHNYC-25JAN26")
        """
        params: dict[str, Any] = {"limit": limit}

        if ticker:
            params["ticker"] = ticker
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts

        logger.info("fetching_kalshi_fills", ticker=ticker)

        data = self._make_request("GET", "/portfolio/fills", params=params)
        return cast(list[dict[str, Any]], data.get("fills", []))

    def get_balance(self) -> dict[str, Any]:
        """Get account balance.

        Returns:
            Balance data dictionary with keys:
            - balance: Available balance in cents
            - portfolio_value: Total portfolio value in cents
            - updated_ts: Last update timestamp

        Example:
            >>> client = KalshiClient(key, secret)
            >>> balance = client.get_balance()
            >>> available = balance["balance"]  # in cents
        """
        logger.info("fetching_kalshi_balance")

        # API returns balance fields directly, not nested
        data = self._make_request("GET", "/portfolio/balance")
        return data

    # =========================================================================
    # Typed Methods (Return Pydantic Models)
    # =========================================================================

    def get_markets_typed(
        self,
        event_ticker: str | None = None,
        series_ticker: str | None = None,
        status: str = "open",
        limit: int = 100,
    ) -> list[Market]:
        """Get list of markets as Pydantic models.

        Args:
            event_ticker: Filter by event ticker
            series_ticker: Filter by series ticker
            status: Market status (open, closed, settled)
            limit: Maximum number of results

        Returns:
            List of Market models

        Example:
            >>> client = KalshiClient(key, secret)
            >>> markets = client.get_markets_typed(series_ticker="HIGHNYC")
            >>> for m in markets:
            ...     print(f"{m.ticker}: spread={m.spread_cents}c")
        """
        raw_markets = self.get_markets(
            event_ticker=event_ticker,
            series_ticker=series_ticker,
            status=status,
            limit=limit,
        )

        markets = []
        for raw in raw_markets:
            try:
                market = Market(
                    ticker=raw.get("ticker", ""),
                    event_ticker=raw.get("event_ticker", ""),
                    title=raw.get("title", ""),
                    subtitle=raw.get("subtitle"),
                    yes_bid=raw.get("yes_bid"),
                    yes_ask=raw.get("yes_ask"),
                    no_bid=raw.get("no_bid"),
                    no_ask=raw.get("no_ask"),
                    last_price=raw.get("last_price"),
                    volume=raw.get("volume", 0),
                    open_interest=raw.get("open_interest", 0),
                    status=raw.get("status", "unknown"),
                    close_time=raw.get("close_time"),
                    expiration_time=raw.get("expiration_time"),
                    result=raw.get("result"),
                    can_close_early=raw.get("can_close_early", False),
                    strike_price=raw.get("strike_price"),
                )
                markets.append(market)
            except Exception as e:
                logger.warning(
                    "market_parse_error",
                    ticker=raw.get("ticker"),
                    error=str(e),
                )

        logger.debug("markets_parsed", count=len(markets))
        return markets

    def get_market_typed(self, ticker: str) -> Market | None:
        """Get single market as Pydantic model.

        Args:
            ticker: Market ticker

        Returns:
            Market model, or None if not found or parse fails

        Example:
            >>> client = KalshiClient(key, secret)
            >>> market = client.get_market_typed("HIGHNYC-25JAN26")
            >>> if market:
            ...     print(f"Spread: {market.spread_cents}c")
        """
        raw = self.get_market(ticker)

        if not raw:
            return None

        try:
            return Market(
                ticker=raw.get("ticker", ""),
                event_ticker=raw.get("event_ticker", ""),
                title=raw.get("title", ""),
                subtitle=raw.get("subtitle"),
                yes_bid=raw.get("yes_bid"),
                yes_ask=raw.get("yes_ask"),
                no_bid=raw.get("no_bid"),
                no_ask=raw.get("no_ask"),
                last_price=raw.get("last_price"),
                volume=raw.get("volume", 0),
                open_interest=raw.get("open_interest", 0),
                status=raw.get("status", "unknown"),
                close_time=raw.get("close_time"),
                expiration_time=raw.get("expiration_time"),
                result=raw.get("result"),
                can_close_early=raw.get("can_close_early", False),
                strike_price=raw.get("strike_price"),
            )
        except Exception as e:
            logger.warning("market_parse_error", ticker=ticker, error=str(e))
            return None

    def get_orderbook_typed(self, ticker: str) -> Orderbook:
        """Get orderbook as Pydantic model.

        Args:
            ticker: Market ticker

        Returns:
            Orderbook model (empty lists if market closed/halted)

        Example:
            >>> client = KalshiClient(key, secret)
            >>> orderbook = client.get_orderbook_typed("HIGHNYC-25JAN26")
            >>> if orderbook.best_yes_bid:
            ...     print(f"Best bid: {orderbook.best_yes_bid}c")
        """
        raw = self.get_orderbook(ticker)

        # Handle empty orderbook (market closed or halted)
        if not raw:
            logger.debug("orderbook_empty", ticker=ticker)
            return Orderbook(yes=[], no=[])

        yes_levels = []
        for level in raw.get("yes", []):
            try:
                yes_levels.append(
                    OrderbookLevel(
                        price=level.get("price", 0),
                        quantity=level.get("count", 0),
                    )
                )
            except Exception as e:
                logger.warning("orderbook_level_parse_error", error=str(e))

        no_levels = []
        for level in raw.get("no", []):
            try:
                no_levels.append(
                    OrderbookLevel(
                        price=level.get("price", 0),
                        quantity=level.get("count", 0),
                    )
                )
            except Exception as e:
                logger.warning("orderbook_level_parse_error", error=str(e))

        return Orderbook(yes=yes_levels, no=no_levels)

    def calculate_spread(self, ticker: str) -> int | None:
        """Calculate bid-ask spread for a market.

        Args:
            ticker: Market ticker

        Returns:
            Spread in cents, or None if pricing unavailable

        Example:
            >>> client = KalshiClient(key, secret)
            >>> spread = client.calculate_spread("HIGHNYC-25JAN26")
            >>> if spread and spread <= 3:
            ...     print("Tight spread - good for trading")
        """
        market = self.get_market_typed(ticker)

        if market is None:
            return None

        spread = market.spread_cents

        logger.debug(
            "spread_calculated",
            ticker=ticker,
            spread_cents=spread,
        )

        return spread
