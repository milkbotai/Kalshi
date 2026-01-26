"""Response models for API clients.

Pydantic models for parsing and validating responses from NWS and Kalshi APIs.
Provides type safety and automatic validation for external API data.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# NWS Response Models
# ============================================================================


class ForecastPeriod(BaseModel):
    """NWS forecast period model.
    
    Represents a single forecast period (e.g., "Tonight", "Wednesday").
    """

    number: int = Field(..., description="Period number")
    name: str = Field(..., description="Period name (e.g., 'Tonight')")
    start_time: datetime = Field(..., description="Period start time")
    end_time: datetime = Field(..., description="Period end time")
    is_daytime: bool = Field(..., description="Whether period is daytime")
    temperature: int = Field(..., description="Temperature in Fahrenheit")
    temperature_unit: str = Field(default="F", description="Temperature unit")
    temperature_trend: str | None = Field(None, description="Temperature trend")
    wind_speed: str = Field(..., description="Wind speed description")
    wind_direction: str = Field(..., description="Wind direction")
    short_forecast: str = Field(..., description="Short forecast description")
    detailed_forecast: str = Field(..., description="Detailed forecast description")
    probability_of_precipitation: dict[str, Any] | None = Field(
        None, description="Precipitation probability"
    )

    class Config:
        """Pydantic config."""

        populate_by_name = True


class Forecast(BaseModel):
    """NWS forecast response model.
    
    Contains multiple forecast periods and metadata.
    """

    updated: datetime = Field(..., description="Forecast update time")
    units: str = Field(default="us", description="Unit system")
    forecast_generator: str = Field(..., description="Forecast generator name")
    generated_at: datetime = Field(..., description="Generation timestamp")
    update_time: datetime = Field(..., description="Update timestamp")
    periods: list[ForecastPeriod] = Field(..., description="Forecast periods")

    class Config:
        """Pydantic config."""

        populate_by_name = True


class Observation(BaseModel):
    """NWS observation model.
    
    Represents current weather conditions from a station.
    """

    timestamp: datetime = Field(..., description="Observation timestamp")
    text_description: str | None = Field(None, description="Text description")
    temperature: float | None = Field(None, description="Temperature in Celsius")
    dewpoint: float | None = Field(None, description="Dewpoint in Celsius")
    wind_direction: int | None = Field(None, description="Wind direction in degrees")
    wind_speed: float | None = Field(None, description="Wind speed in km/h")
    wind_gust: float | None = Field(None, description="Wind gust in km/h")
    barometric_pressure: float | None = Field(None, description="Pressure in Pa")
    sea_level_pressure: float | None = Field(None, description="Sea level pressure in Pa")
    visibility: float | None = Field(None, description="Visibility in meters")
    relative_humidity: float | None = Field(None, description="Relative humidity %")
    heat_index: float | None = Field(None, description="Heat index in Celsius")
    wind_chill: float | None = Field(None, description="Wind chill in Celsius")

    @field_validator("temperature", "dewpoint", "heat_index", "wind_chill", mode="before")
    @classmethod
    def extract_value(cls, v: Any) -> float | None:
        """Extract value from NWS value object.
        
        NWS returns values as {"value": 20.5, "unitCode": "wmoUnit:degC"}.
        """
        if v is None:
            return None
        if isinstance(v, dict):
            return v.get("value")
        return v

    class Config:
        """Pydantic config."""

        populate_by_name = True


# ============================================================================
# Kalshi Response Models
# ============================================================================


class Market(BaseModel):
    """Kalshi market model.
    
    Represents a prediction market on Kalshi.
    """

    ticker: str = Field(..., description="Market ticker")
    event_ticker: str = Field(..., description="Parent event ticker")
    title: str = Field(..., description="Market title")
    subtitle: str | None = Field(None, description="Market subtitle")
    yes_bid: int | None = Field(None, description="Yes bid price in cents")
    yes_ask: int | None = Field(None, description="Yes ask price in cents")
    no_bid: int | None = Field(None, description="No bid price in cents")
    no_ask: int | None = Field(None, description="No ask price in cents")
    last_price: int | None = Field(None, description="Last traded price in cents")
    volume: int = Field(default=0, description="Total volume")
    open_interest: int = Field(default=0, description="Open interest")
    status: str = Field(..., description="Market status")
    close_time: datetime | None = Field(None, description="Market close time")
    expiration_time: datetime | None = Field(None, description="Expiration time")
    result: str | None = Field(None, description="Market result")
    can_close_early: bool = Field(default=False, description="Can close early")
    strike_price: float | None = Field(None, description="Strike price for numeric markets")

    @property
    def spread_cents(self) -> int | None:
        """Calculate bid-ask spread in cents.
        
        Returns:
            Spread in cents, or None if pricing unavailable
        """
        if self.yes_bid is not None and self.yes_ask is not None:
            return self.yes_ask - self.yes_bid
        return None

    @property
    def mid_price(self) -> float | None:
        """Calculate mid price.
        
        Returns:
            Mid price in cents, or None if pricing unavailable
        """
        if self.yes_bid is not None and self.yes_ask is not None:
            return (self.yes_bid + self.yes_ask) / 2.0
        return None

    class Config:
        """Pydantic config."""

        populate_by_name = True


class OrderbookLevel(BaseModel):
    """Orderbook price level.
    
    Represents a single price level in the orderbook.
    """

    price: int = Field(..., description="Price in cents")
    quantity: int = Field(..., description="Quantity available")

    class Config:
        """Pydantic config."""

        populate_by_name = True


class Orderbook(BaseModel):
    """Kalshi orderbook model.
    
    Contains bid and ask levels for yes and no sides.
    """

    yes: list[OrderbookLevel] = Field(default_factory=list, description="Yes side levels")
    no: list[OrderbookLevel] = Field(default_factory=list, description="No side levels")

    @property
    def best_yes_bid(self) -> int | None:
        """Get best yes bid price.
        
        Returns:
            Best bid price in cents, or None if no bids
        """
        if self.yes:
            return max(level.price for level in self.yes)
        return None

    @property
    def best_yes_ask(self) -> int | None:
        """Get best yes ask price.
        
        Returns:
            Best ask price in cents, or None if no asks
        """
        if self.yes:
            return min(level.price for level in self.yes)
        return None

    class Config:
        """Pydantic config."""

        populate_by_name = True


class Order(BaseModel):
    """Kalshi order model.
    
    Represents a trading order on Kalshi.
    """

    order_id: str = Field(..., description="Kalshi order ID")
    ticker: str = Field(..., description="Market ticker")
    side: str = Field(..., description="Order side (yes/no)")
    action: str = Field(..., description="Order action (buy/sell)")
    count: int = Field(..., description="Number of contracts")
    yes_price: int | None = Field(None, description="Yes price in cents")
    no_price: int | None = Field(None, description="No price in cents")
    status: str = Field(..., description="Order status")
    created_time: datetime = Field(..., description="Order creation time")
    expiration_time: datetime | None = Field(None, description="Order expiration time")
    client_order_id: str | None = Field(None, description="Client order ID")
    remaining_count: int | None = Field(None, description="Remaining contracts")
    filled_count: int | None = Field(None, description="Filled contracts")

    @property
    def is_filled(self) -> bool:
        """Check if order is fully filled.
        
        Returns:
            True if order is completely filled
        """
        if self.filled_count is not None and self.count is not None:
            return self.filled_count >= self.count
        return self.status == "filled"

    class Config:
        """Pydantic config."""

        populate_by_name = True


class Position(BaseModel):
    """Kalshi position model.
    
    Represents a current position in a market.
    """

    ticker: str = Field(..., description="Market ticker")
    position: int = Field(..., description="Net position (positive=long, negative=short)")
    total_cost: int = Field(..., description="Total cost basis in cents")
    fees_paid: int = Field(default=0, description="Fees paid in cents")
    resting_orders_count: int = Field(default=0, description="Number of resting orders")

    @property
    def average_price(self) -> float | None:
        """Calculate average entry price.
        
        Returns:
            Average price in cents, or None if no position
        """
        if self.position != 0:
            return self.total_cost / abs(self.position)
        return None

    class Config:
        """Pydantic config."""

        populate_by_name = True


class Fill(BaseModel):
    """Kalshi fill model.
    
    Represents a trade execution (fill).
    """

    fill_id: str = Field(..., description="Fill ID")
    order_id: str = Field(..., description="Order ID")
    ticker: str = Field(..., description="Market ticker")
    side: str = Field(..., description="Fill side (yes/no)")
    action: str = Field(..., description="Fill action (buy/sell)")
    count: int = Field(..., description="Number of contracts filled")
    yes_price: int | None = Field(None, description="Yes price in cents")
    no_price: int | None = Field(None, description="No price in cents")
    created_time: datetime = Field(..., description="Fill timestamp")
    trade_id: str | None = Field(None, description="Trade ID")

    @property
    def price(self) -> int:
        """Get fill price.
        
        Returns:
            Fill price in cents
        """
        if self.side == "yes":
            return self.yes_price or 0
        else:
            return self.no_price or 0

    @property
    def notional_value(self) -> int:
        """Calculate notional value.
        
        Returns:
            Notional value in cents
        """
        return self.price * self.count

    class Config:
        """Pydantic config."""

        populate_by_name = True


class Balance(BaseModel):
    """Kalshi balance model.
    
    Represents account balance information.
    """

    balance: int = Field(..., description="Total balance in cents")
    payout: int = Field(default=0, description="Pending payout in cents")

    @property
    def available_balance(self) -> int:
        """Calculate available balance.
        
        Returns:
            Available balance in cents
        """
        return self.balance - self.payout

    class Config:
        """Pydantic config."""

        populate_by_name = True
