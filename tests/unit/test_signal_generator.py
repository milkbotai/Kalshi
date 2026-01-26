"""Unit tests for signal generator."""

import pytest

from src.analytics.signal_generator import Signal, SignalGenerator
from src.shared.api.response_models import Market


class TestSignal:
    """Test suite for Signal dataclass."""

    def test_signal_creation(self) -> None:
        """Test creating a Signal instance."""
        signal = Signal(
            ticker="HIGHNYC-25JAN26",
            side="yes",
            confidence=0.75,
            reason="Forecast above strike",
        )

        assert signal.ticker == "HIGHNYC-25JAN26"
        assert signal.side == "yes"
        assert signal.confidence == 0.75
        assert signal.reason == "Forecast above strike"

    def test_signal_with_features(self) -> None:
        """Test Signal with features dictionary."""
        signal = Signal(
            ticker="TEST-01",
            side="no",
            confidence=0.65,
            reason="Test",
            features={"temp_diff": -5.0},
        )

        assert signal.features is not None
        assert signal.features["temp_diff"] == -5.0

    def test_signal_validates_confidence_range(self) -> None:
        """Test Signal validates confidence is between 0 and 1."""
        with pytest.raises(ValueError, match="Confidence must be between 0 and 1"):
            Signal(
                ticker="TEST-01",
                side="yes",
                confidence=1.5,
                reason="Test",
            )

    def test_signal_validates_side(self) -> None:
        """Test Signal validates side is yes or no."""
        with pytest.raises(ValueError, match="Side must be 'yes' or 'no'"):
            Signal(
                ticker="TEST-01",
                side="invalid",
                confidence=0.75,
                reason="Test",
            )


class TestSignalGenerator:
    """Test suite for SignalGenerator."""

    @pytest.fixture
    def generator(self) -> SignalGenerator:
        """Create signal generator instance."""
        return SignalGenerator(min_confidence=0.6)

    @pytest.fixture
    def sample_market(self) -> Market:
        """Create sample market."""
        return Market(
            ticker="HIGHNYC-25JAN26",
            event_ticker="HIGHNYC",
            title="Will NYC high be above 32F?",
            yes_bid=45,
            yes_ask=48,
            volume=1000,
            open_interest=5000,
            status="open",
            strike_price=32.0,
        )

    def test_generator_initialization(self, generator: SignalGenerator) -> None:
        """Test SignalGenerator initializes with min confidence."""
        assert generator.min_confidence == 0.6

    def test_generate_temperature_signal_above_strike(
        self, generator: SignalGenerator, sample_market: Market
    ) -> None:
        """Test generating temperature signal when forecast above strike."""
        weather = {"temperature": 42.0}  # 10°F above strike

        signal = generator.generate_temperature_signal(weather, sample_market)

        assert signal is not None
        assert signal.ticker == "HIGHNYC-25JAN26"
        assert signal.side == "yes"
        assert signal.confidence >= 0.6
        assert "above strike" in signal.reason.lower()

    def test_generate_temperature_signal_below_strike(
        self, generator: SignalGenerator, sample_market: Market
    ) -> None:
        """Test generating temperature signal when forecast below strike."""
        weather = {"temperature": 22.0}  # 10°F below strike

        signal = generator.generate_temperature_signal(weather, sample_market)

        assert signal is not None
        assert signal.side == "no"
        assert signal.confidence >= 0.6
        assert "below strike" in signal.reason.lower()

    def test_generate_temperature_signal_low_confidence(
        self, generator: SignalGenerator, sample_market: Market
    ) -> None:
        """Test temperature signal returns None when confidence too low."""
        weather = {"temperature": 34.0}  # Only 2°F above strike

        signal = generator.generate_temperature_signal(weather, sample_market)

        # Confidence too low, should return None
        assert signal is None

    def test_generate_temperature_signal_missing_data(
        self, generator: SignalGenerator, sample_market: Market
    ) -> None:
        """Test temperature signal handles missing data."""
        weather = {}  # No temperature data

        signal = generator.generate_temperature_signal(weather, sample_market)

        assert signal is None

    def test_generate_temperature_signal_no_strike_price(
        self, generator: SignalGenerator
    ) -> None:
        """Test temperature signal handles market without strike price."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            status="open",
            strike_price=None,
        )
        weather = {"temperature": 72.0}

        signal = generator.generate_temperature_signal(weather, market)

        assert signal is None

    def test_generate_precipitation_signal_high_probability(
        self, generator: SignalGenerator, sample_market: Market
    ) -> None:
        """Test generating precipitation signal with high probability."""
        weather = {"precipitation_probability": 0.70}

        signal = generator.generate_precipitation_signal(weather, sample_market)

        assert signal is not None
        assert signal.ticker == "HIGHNYC-25JAN26"
        assert signal.side == "no"  # Precipitation lowers high temps
        assert signal.confidence >= 0.6

    def test_generate_precipitation_signal_low_probability(
        self, generator: SignalGenerator, sample_market: Market
    ) -> None:
        """Test precipitation signal returns None for low probability."""
        weather = {"precipitation_probability": 0.10}

        signal = generator.generate_precipitation_signal(weather, sample_market)

        assert signal is None

    def test_generate_precipitation_signal_missing_data(
        self, generator: SignalGenerator, sample_market: Market
    ) -> None:
        """Test precipitation signal handles missing data."""
        weather = {}

        signal = generator.generate_precipitation_signal(weather, sample_market)

        assert signal is None

    def test_calculate_confidence_score_high_quality(
        self, generator: SignalGenerator, sample_market: Market
    ) -> None:
        """Test confidence score calculation with high quality data."""
        weather = {
            "temperature": 72.0,
            "precipitation_probability": 0.2,
        }

        score = generator.calculate_confidence_score(weather, sample_market)

        # Should have high score due to good market and data quality
        assert score >= 0.7

    def test_calculate_confidence_score_low_quality_market(
        self, generator: SignalGenerator
    ) -> None:
        """Test confidence score with low quality market."""
        market = Market(
            ticker="TEST-01",
            event_ticker="TEST",
            title="Test",
            yes_bid=40,
            yes_ask=50,  # Wide spread
            volume=10,
            open_interest=50,
            status="open",
        )
        weather = {"temperature": 72.0}

        score = generator.calculate_confidence_score(weather, market)

        # Should have lower score due to poor market quality
        assert score < 0.6

    def test_calculate_confidence_score_missing_weather_data(
        self, generator: SignalGenerator, sample_market: Market
    ) -> None:
        """Test confidence score with missing weather data."""
        weather = {}  # No data

        score = generator.calculate_confidence_score(weather, sample_market)

        # Should have lower score due to missing data
        assert score < 0.5

    def test_combine_signals_consensus_yes(self, generator: SignalGenerator) -> None:
        """Test combining signals with yes consensus."""
        signals = [
            Signal(ticker="TEST-01", side="yes", confidence=0.7, reason="Reason 1"),
            Signal(ticker="TEST-01", side="yes", confidence=0.8, reason="Reason 2"),
            Signal(ticker="TEST-01", side="no", confidence=0.6, reason="Reason 3"),
        ]

        combined = generator.combine_signals(signals)

        assert combined is not None
        assert combined.side == "yes"
        assert combined.confidence == 0.75  # Average of 0.7 and 0.8
        assert "Reason 1" in combined.reason
        assert "Reason 2" in combined.reason

    def test_combine_signals_consensus_no(self, generator: SignalGenerator) -> None:
        """Test combining signals with no consensus."""
        signals = [
            Signal(ticker="TEST-01", side="no", confidence=0.7, reason="Reason 1"),
            Signal(ticker="TEST-01", side="no", confidence=0.8, reason="Reason 2"),
            Signal(ticker="TEST-01", side="yes", confidence=0.6, reason="Reason 3"),
        ]

        combined = generator.combine_signals(signals)

        assert combined is not None
        assert combined.side == "no"
        assert combined.confidence == 0.75

    def test_combine_signals_no_consensus(self, generator: SignalGenerator) -> None:
        """Test combining signals with no majority."""
        signals = [
            Signal(ticker="TEST-01", side="yes", confidence=0.7, reason="Reason 1"),
            Signal(ticker="TEST-01", side="no", confidence=0.8, reason="Reason 2"),
        ]

        combined = generator.combine_signals(signals)

        # No consensus, should return None
        assert combined is None

    def test_combine_signals_empty_list(self, generator: SignalGenerator) -> None:
        """Test combining empty signal list."""
        combined = generator.combine_signals([])

        assert combined is None

    def test_combine_signals_single_signal(self, generator: SignalGenerator) -> None:
        """Test combining single signal."""
        signals = [
            Signal(ticker="TEST-01", side="yes", confidence=0.75, reason="Only signal")
        ]

        combined = generator.combine_signals(signals)

        assert combined is not None
        assert combined.side == "yes"
        assert combined.confidence == 0.75

    def test_combine_signals_merges_features(self, generator: SignalGenerator) -> None:
        """Test combining signals merges feature dictionaries."""
        signals = [
            Signal(
                ticker="TEST-01",
                side="yes",
                confidence=0.7,
                reason="R1",
                features={"temp_diff": 5.0},
            ),
            Signal(
                ticker="TEST-01",
                side="yes",
                confidence=0.8,
                reason="R2",
                features={"precip_prob": 0.2},
            ),
        ]

        combined = generator.combine_signals(signals)

        assert combined is not None
        assert combined.features is not None
        assert "temp_diff" in combined.features
        assert "precip_prob" in combined.features
