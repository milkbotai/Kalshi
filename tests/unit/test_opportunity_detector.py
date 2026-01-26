"""Unit tests for market opportunity detector."""

from datetime import date, datetime, timezone

import pytest

from src.analytics.opportunity_detector import OpportunityDetector
from src.shared.api.response_models import Market


class TestOpportunityDetector:
    """Test suite for OpportunityDetector."""

    @pytest.fixture
    def detector(self) -> OpportunityDetector:
        """Create opportunity detector instance."""
        return OpportunityDetector()

    @pytest.fixture
    def sample_markets(self) -> list[Market]:
        """Create sample markets for testing."""
        return [
            Market(
                ticker="HIGHNYC-25JAN26",
                event_ticker="HIGHNYC",
                title="Will NYC high be above 32F?",
                yes_bid=45,
                yes_ask=48,
                volume=1000,
                open_interest=5000,
                status="open",
                expiration_time=datetime(2026, 1, 26, tzinfo=timezone.utc),
            ),
            Market(
                ticker="HIGHCHI-25JAN26",
                event_ticker="HIGHCHI",
                title="Will Chicago high be above 20F?",
                yes_bid=50,
                yes_ask=54,
                volume=500,
                open_interest=2000,
                status="open",
                expiration_time=datetime(2026, 1, 26, tzinfo=timezone.utc),
            ),
            Market(
                ticker="HIGHLAX-25JAN26",
                event_ticker="HIGHLAX",
                title="Will LA high be above 60F?",
                yes_bid=70,
                yes_ask=75,
                volume=200,
                open_interest=1000,
                status="open",
                expiration_time=datetime(2026, 1, 26, tzinfo=timezone.utc),
            ),
        ]

    def test_detector_initialization(self, detector: OpportunityDetector) -> None:
        """Test OpportunityDetector initializes correctly."""
        assert detector is not None

    def test_find_weather_markets_by_city(
        self, detector: OpportunityDetector, sample_markets: list[Market]
    ) -> None:
        """Test finding markets by city code."""
        result = detector.find_weather_markets("NYC", sample_markets)

        assert len(result) == 1
        assert result[0].ticker == "HIGHNYC-25JAN26"

    def test_find_weather_markets_by_keyword(
        self, detector: OpportunityDetector, sample_markets: list[Market]
    ) -> None:
        """Test finding markets by keyword in title."""
        result = detector.find_weather_markets("high", sample_markets)

        # Should match all markets with "high" in title
        assert len(result) == 3

    def test_find_weather_markets_case_insensitive(
        self, detector: OpportunityDetector, sample_markets: list[Market]
    ) -> None:
        """Test market search is case insensitive."""
        result1 = detector.find_weather_markets("nyc", sample_markets)
        result2 = detector.find_weather_markets("NYC", sample_markets)

        assert len(result1) == len(result2)
        assert result1[0].ticker == result2[0].ticker

    def test_find_weather_markets_no_matches(
        self, detector: OpportunityDetector, sample_markets: list[Market]
    ) -> None:
        """Test finding markets with no matches."""
        result = detector.find_weather_markets("INVALID", sample_markets)

        assert len(result) == 0

    def test_match_city_to_markets(
        self, detector: OpportunityDetector, sample_markets: list[Market]
    ) -> None:
        """Test matching markets to specific city."""
        result = detector.match_city_to_markets("NYC", sample_markets)

        assert len(result) == 1
        assert result[0].ticker == "HIGHNYC-25JAN26"

    def test_match_city_to_markets_multiple(
        self, detector: OpportunityDetector
    ) -> None:
        """Test matching city with multiple markets."""
        markets = [
            Market(
                ticker="HIGHNYC-25JAN26",
                event_ticker="HIGHNYC",
                title="NYC High",
                status="open",
            ),
            Market(
                ticker="HIGHNYC-26JAN26",
                event_ticker="HIGHNYC",
                title="NYC High",
                status="open",
            ),
        ]

        result = detector.match_city_to_markets("NYC", markets)

        assert len(result) == 2

    def test_filter_by_date_range(
        self, detector: OpportunityDetector, sample_markets: list[Market]
    ) -> None:
        """Test filtering markets by date range."""
        start = date(2026, 1, 25)
        end = date(2026, 1, 27)

        result = detector.filter_by_date_range(sample_markets, start, end)

        # All sample markets expire on 2026-01-26
        assert len(result) == 3

    def test_filter_by_date_range_excludes_outside(
        self, detector: OpportunityDetector, sample_markets: list[Market]
    ) -> None:
        """Test date range filter excludes markets outside range."""
        start = date(2026, 1, 27)
        end = date(2026, 1, 28)

        result = detector.filter_by_date_range(sample_markets, start, end)

        assert len(result) == 0

    def test_filter_by_date_range_handles_null_expiration(
        self, detector: OpportunityDetector
    ) -> None:
        """Test date range filter handles markets with null expiration."""
        markets = [
            Market(
                ticker="TEST-01",
                event_ticker="TEST",
                title="Test",
                status="open",
                expiration_time=None,
            )
        ]

        result = detector.filter_by_date_range(
            markets, date(2026, 1, 25), date(2026, 1, 27)
        )

        assert len(result) == 0

    def test_calculate_market_relevance_score_high_liquidity(
        self, detector: OpportunityDetector, sample_markets: list[Market]
    ) -> None:
        """Test relevance score calculation with high liquidity."""
        market = sample_markets[0]  # NYC market with 6000 total liquidity
        weather = {}

        score = detector.calculate_market_relevance_score(market, weather)

        # Should have high score due to liquidity and tight spread
        assert score >= 0.7

    def test_calculate_market_relevance_score_low_liquidity(
        self, detector: OpportunityDetector
    ) -> None:
        """Test relevance score calculation with low liquidity."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=45,
            yes_ask=48,
            volume=10,
            open_interest=50,
            status="open",
        )
        weather = {}

        score = detector.calculate_market_relevance_score(market, weather)

        # Should have lower score due to low liquidity
        assert score < 0.5

    def test_calculate_market_relevance_score_wide_spread(
        self, detector: OpportunityDetector
    ) -> None:
        """Test relevance score penalizes wide spreads."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=40,
            yes_ask=50,  # 10 cent spread
            volume=1000,
            open_interest=5000,
            status="open",
        )
        weather = {}

        score = detector.calculate_market_relevance_score(market, weather)

        # Should have lower score due to wide spread
        assert score < 0.8

    def test_calculate_market_relevance_score_closed_market(
        self, detector: OpportunityDetector
    ) -> None:
        """Test relevance score for closed market."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=45,
            yes_ask=48,
            volume=1000,
            open_interest=5000,
            status="closed",
        )
        weather = {}

        score = detector.calculate_market_relevance_score(market, weather)

        # Should have lower score due to closed status
        assert score < 0.7

    def test_detect_opportunities(
        self, detector: OpportunityDetector, sample_markets: list[Market]
    ) -> None:
        """Test detecting opportunities from weather and markets."""
        weather = {"temperature": 72.0, "precipitation_probability": 0.1}

        opportunities = detector.detect_opportunities(weather, sample_markets)

        # Should return opportunities sorted by score
        assert len(opportunities) > 0
        assert all(isinstance(opp, tuple) for opp in opportunities)
        assert all(len(opp) == 2 for opp in opportunities)
        
        # Verify sorted by score descending
        scores = [score for _, score in opportunities]
        assert scores == sorted(scores, reverse=True)

    def test_detect_opportunities_filters_low_scores(
        self, detector: OpportunityDetector
    ) -> None:
        """Test opportunity detection filters out low-scoring markets."""
        markets = [
            Market(
                ticker="TEST-01",
                event_ticker="TEST",
                title="Test",
                volume=0,
                open_interest=0,
                status="closed",
            )
        ]
        weather = {}

        opportunities = detector.detect_opportunities(weather, markets)

        # Low-scoring market should be filtered out
        assert len(opportunities) == 0

    def test_detect_opportunities_empty_markets(
        self, detector: OpportunityDetector
    ) -> None:
        """Test opportunity detection with empty market list."""
        weather = {}

        opportunities = detector.detect_opportunities(weather, [])

        assert len(opportunities) == 0
