"""Market opportunity detector for identifying tradeable weather markets.

Matches weather data to relevant Kalshi markets and calculates
relevance scores for trading opportunities.
"""

from datetime import date
from typing import Any

from src.shared.api.response_models import Market
from src.shared.config.logging import get_logger

logger = get_logger(__name__)


class OpportunityDetector:
    """Detects trading opportunities by matching weather data to markets.
    
    Filters and scores markets based on relevance to current weather
    conditions and forecast data.
    """

    def __init__(self) -> None:
        """Initialize opportunity detector."""
        logger.info("opportunity_detector_initialized")

    def find_weather_markets(
        self, query: str, markets: list[Market]
    ) -> list[Market]:
        """Find markets matching a search query.
        
        Args:
            query: Search query (e.g., "NYC", "temperature", "rain")
            markets: List of markets to search
            
        Returns:
            Filtered list of markets matching query
            
        Example:
            >>> detector = OpportunityDetector()
            >>> nyc_markets = detector.find_weather_markets("NYC", all_markets)
        """
        query_lower = query.lower()
        
        filtered = [
            market
            for market in markets
            if query_lower in market.ticker.lower()
            or query_lower in market.title.lower()
            or query_lower in market.event_ticker.lower()
        ]
        
        logger.debug(
            "weather_markets_found",
            query=query,
            total_markets=len(markets),
            filtered_count=len(filtered),
        )
        
        return filtered

    def match_city_to_markets(
        self, city: str, markets: list[Market]
    ) -> list[Market]:
        """Match markets to a specific city.
        
        Args:
            city: 3-letter city code (e.g., "NYC")
            markets: List of markets to filter
            
        Returns:
            Markets relevant to the specified city
            
        Example:
            >>> detector = OpportunityDetector()
            >>> nyc_markets = detector.match_city_to_markets("NYC", all_markets)
        """
        city_upper = city.upper()
        
        matched = [
            market
            for market in markets
            if city_upper in market.ticker.upper()
            or city_upper in market.event_ticker.upper()
        ]
        
        logger.info(
            "city_markets_matched",
            city=city,
            matched_count=len(matched),
        )
        
        return matched

    def filter_by_date_range(
        self,
        markets: list[Market],
        start: date,
        end: date,
    ) -> list[Market]:
        """Filter markets by expiration date range.
        
        Args:
            markets: List of markets to filter
            start: Start date (inclusive)
            end: End date (inclusive)
            
        Returns:
            Markets expiring within the date range
        """
        filtered = []
        
        for market in markets:
            if market.expiration_time is None:
                continue
            
            exp_date = market.expiration_time.date()
            if start <= exp_date <= end:
                filtered.append(market)
        
        logger.debug(
            "markets_filtered_by_date",
            start=start,
            end=end,
            filtered_count=len(filtered),
        )
        
        return filtered

    def calculate_market_relevance_score(
        self, market: Market, weather: dict[str, Any]
    ) -> float:
        """Calculate relevance score for a market given weather data.
        
        Args:
            market: Market to score
            weather: Weather data dictionary
            
        Returns:
            Relevance score from 0.0 to 1.0
            
        Note:
            Score based on:
            - Market liquidity (volume + open interest)
            - Spread tightness
            - Time to expiration
        """
        score = 0.0
        
        # Liquidity component (0-0.4)
        total_liquidity = market.volume + market.open_interest
        if total_liquidity > 0:
            # Normalize: 1000+ contracts = max score
            liquidity_score = min(total_liquidity / 1000.0, 1.0) * 0.4
            score += liquidity_score
        
        # Spread component (0-0.3)
        if market.spread_cents is not None:
            # Tighter spread = higher score
            # 1 cent spread = max, 5+ cents = min
            spread_score = max(0.0, (5.0 - market.spread_cents) / 5.0) * 0.3
            score += spread_score
        
        # Market status component (0-0.3)
        if market.status == "open":
            score += 0.3
        
        logger.debug(
            "market_relevance_calculated",
            ticker=market.ticker,
            score=score,
            liquidity=total_liquidity,
            spread=market.spread_cents,
        )
        
        return min(score, 1.0)

    def detect_opportunities(
        self, weather_data: dict[str, Any], markets: list[Market]
    ) -> list[tuple[Market, float]]:
        """Detect trading opportunities from weather and market data.
        
        Args:
            weather_data: Normalized weather data dictionary
            markets: List of markets to evaluate
            
        Returns:
            List of (market, relevance_score) tuples, sorted by score descending
            
        Example:
            >>> detector = OpportunityDetector()
            >>> opportunities = detector.detect_opportunities(weather, markets)
            >>> best_market, score = opportunities[0]
        """
        opportunities = []
        
        for market in markets:
            score = self.calculate_market_relevance_score(market, weather_data)
            
            # Only include markets with meaningful relevance
            if score >= 0.3:
                opportunities.append((market, score))
        
        # Sort by score descending
        opportunities.sort(key=lambda x: x[1], reverse=True)
        
        logger.info(
            "opportunities_detected",
            total_markets=len(markets),
            opportunities_found=len(opportunities),
        )
        
        return opportunities
