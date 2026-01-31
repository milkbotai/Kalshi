"""Tests for dashboard components module."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, call
import pandas as pd

from src.dashboard.components import (
    render_city_grid,
    render_city_card,
    render_equity_chart,
    render_trade_feed,
    render_performance_heatmap,
    render_health_indicator,
)
from src.dashboard.data import CityMarketData


@pytest.fixture
def mock_streamlit():
    """Mock streamlit functions."""
    with patch("src.dashboard.components.st") as mock_st:
        # Mock container
        mock_container = Mock()
        mock_container.__enter__ = Mock(return_value=mock_container)
        mock_container.__exit__ = Mock(return_value=False)
        mock_st.container = Mock(return_value=mock_container)
        
        # Mock columns
        mock_col = Mock()
        mock_st.columns = Mock(return_value=[mock_col, mock_col, mock_col, mock_col, mock_col])
        
        # Mock UI elements
        mock_st.markdown = Mock()
        mock_st.caption = Mock()
        mock_st.metric = Mock()
        mock_st.write = Mock()
        mock_st.divider = Mock()
        mock_st.warning = Mock()
        mock_st.info = Mock()
        mock_st.success = Mock()
        mock_st.error = Mock()
        mock_st.plotly_chart = Mock()
        mock_st.dataframe = Mock()
        mock_st.subheader = Mock()
        
        # Mock expander
        mock_expander = Mock()
        mock_expander.__enter__ = Mock(return_value=mock_expander)
        mock_expander.__exit__ = Mock(return_value=False)
        mock_st.expander = Mock(return_value=mock_expander)
        
        yield mock_st


@pytest.fixture
def sample_city_data():
    """Create sample city market data."""
    return [
        CityMarketData(
            city_code="NYC",
            city_name="New York City",
            current_temp=72.5,
            yes_bid=45,
            yes_ask=48,
            spread=3,
            volume=1500,
            last_signal="BUY",
        ),
        CityMarketData(
            city_code="CHI",
            city_name="Chicago",
            current_temp=65.0,
            yes_bid=50,
            yes_ask=53,
            spread=3,
            volume=1200,
            last_signal="SELL",
        ),
        CityMarketData(
            city_code="LAX",
            city_name="Los Angeles",
            current_temp=None,
            yes_bid=None,
            yes_ask=None,
            spread=None,
            volume=None,
            last_signal=None,
        ),
        CityMarketData(
            city_code="MIA",
            city_name="Miami",
            current_temp=80.0,
            yes_bid=40,
            yes_ask=46,
            spread=6,
            volume=800,
            last_signal="HOLD",
        ),
        CityMarketData(
            city_code="SEA",
            city_name="Seattle",
            current_temp=55.0,
            yes_bid=48,
            yes_ask=52,
            spread=4,
            volume=1000,
            last_signal="BUY",
        ),
        CityMarketData(
            city_code="DEN",
            city_name="Denver",
            current_temp=60.0,
            yes_bid=42,
            yes_ask=50,
            spread=8,
            volume=600,
            last_signal="SELL",
        ),
        CityMarketData(
            city_code="ATL",
            city_name="Atlanta",
            current_temp=75.0,
            yes_bid=44,
            yes_ask=47,
            spread=3,
            volume=1100,
            last_signal="BUY",
        ),
        CityMarketData(
            city_code="PHX",
            city_name="Phoenix",
            current_temp=95.0,
            yes_bid=35,
            yes_ask=38,
            spread=3,
            volume=900,
            last_signal="SELL",
        ),
        CityMarketData(
            city_code="BOS",
            city_name="Boston",
            current_temp=68.0,
            yes_bid=46,
            yes_ask=49,
            spread=3,
            volume=1300,
            last_signal="BUY",
        ),
        CityMarketData(
            city_code="DAL",
            city_name="Dallas",
            current_temp=85.0,
            yes_bid=38,
            yes_ask=42,
            spread=4,
            volume=700,
            last_signal="HOLD",
        ),
    ]


class TestRenderCityGrid:
    """Tests for render_city_grid function."""
    
    @patch("src.dashboard.components.render_city_card")
    def test_renders_empty_grid(self, mock_render_card, mock_streamlit):
        """Test that empty grid shows warning."""
        render_city_grid([])
        
        mock_streamlit.warning.assert_called_with("No city data available")
        mock_render_card.assert_not_called()
    
    @patch("src.dashboard.components.render_city_card")
    def test_renders_10_city_grid(self, mock_render_card, mock_streamlit, sample_city_data):
        """Test that 10-city grid is rendered correctly."""
        render_city_grid(sample_city_data)
        
        # Check columns were created twice (2 rows)
        assert mock_streamlit.columns.call_count == 2
        
        # Check all 10 cities were rendered
        assert mock_render_card.call_count == 10


class TestRenderCityCard:
    """Tests for render_city_card function."""
    
    def test_renders_city_card_with_all_data(self, mock_streamlit):
        """Test that city card renders with all data."""
        city = CityMarketData(
            city_code="NYC",
            city_name="New York City",
            current_temp=72.5,
            yes_bid=45,
            yes_ask=48,
            spread=3,
            volume=1500,
            last_signal="BUY",
        )
        
        render_city_card(city)
        
        # Check markdown was called for city code
        mock_streamlit.markdown.assert_called()
        
        # Check caption was called for city name
        mock_streamlit.caption.assert_called_with("New York City")
        
        # Check metric was called for temperature
        mock_streamlit.metric.assert_called()
        
        # Check write was called for bid/ask, spread, volume, signal
        assert mock_streamlit.write.call_count >= 3
        
        # Check divider was called
        mock_streamlit.divider.assert_called()
    
    def test_renders_city_card_with_missing_data(self, mock_streamlit):
        """Test that city card handles missing data."""
        city = CityMarketData(
            city_code="LAX",
            city_name="Los Angeles",
            current_temp=None,
            yes_bid=None,
            yes_ask=None,
            spread=None,
            volume=None,
            last_signal=None,
        )
        
        render_city_card(city)
        
        # Check N/A values were displayed
        mock_streamlit.metric.assert_called()
        mock_streamlit.write.assert_called()
    
    def test_renders_city_card_spread_colors(self, mock_streamlit):
        """Test that spread colors are applied correctly."""
        # Green spread (<=3)
        city_green = CityMarketData(
            city_code="NYC",
            city_name="New York City",
            current_temp=72.5,
            yes_bid=45,
            yes_ask=48,
            spread=3,
            volume=1500,
            last_signal="BUY",
        )
        render_city_card(city_green)
        
        # Orange spread (4-5)
        city_orange = CityMarketData(
            city_code="CHI",
            city_name="Chicago",
            current_temp=65.0,
            yes_bid=50,
            yes_ask=54,
            spread=4,
            volume=1200,
            last_signal="SELL",
        )
        render_city_card(city_orange)
        
        # Red spread (>5)
        city_red = CityMarketData(
            city_code="MIA",
            city_name="Miami",
            current_temp=80.0,
            yes_bid=40,
            yes_ask=47,
            spread=7,
            volume=800,
            last_signal="HOLD",
        )
        render_city_card(city_red)
        
        # Check markdown was called with color styling
        assert mock_streamlit.markdown.call_count >= 3
    
    def test_renders_city_card_signal_colors(self, mock_streamlit):
        """Test that signal colors are applied correctly."""
        # BUY signal (green)
        city_buy = CityMarketData(
            city_code="NYC",
            city_name="New York City",
            current_temp=72.5,
            yes_bid=45,
            yes_ask=48,
            spread=3,
            volume=1500,
            last_signal="BUY",
        )
        render_city_card(city_buy)
        
        # SELL signal (red)
        city_sell = CityMarketData(
            city_code="CHI",
            city_name="Chicago",
            current_temp=65.0,
            yes_bid=50,
            yes_ask=53,
            spread=3,
            volume=1200,
            last_signal="SELL",
        )
        render_city_card(city_sell)
        
        # HOLD signal (gray)
        city_hold = CityMarketData(
            city_code="MIA",
            city_name="Miami",
            current_temp=80.0,
            yes_bid=40,
            yes_ask=46,
            spread=6,
            volume=800,
            last_signal="HOLD",
        )
        render_city_card(city_hold)
        
        # Check markdown was called with signal styling
        assert mock_streamlit.markdown.call_count >= 3


class TestRenderEquityChart:
    """Tests for render_equity_chart function."""
    
    def test_renders_empty_equity_chart(self, mock_streamlit):
        """Test that empty equity chart shows info message."""
        render_equity_chart([])
        
        mock_streamlit.info.assert_called_with("No equity data available")
        mock_streamlit.plotly_chart.assert_not_called()
    
    def test_renders_equity_chart_with_data(self, mock_streamlit):
        """Test that equity chart renders with data."""
        equity_data = [
            {
                "date": "2024-01-01",
                "ending_equity": 5100.0,
                "daily_pnl": 100.0,
                "cumulative_pnl": 100.0,
                "high_water_mark": 5100.0,
                "drawdown_pct": 0.0,
            },
            {
                "date": "2024-01-02",
                "ending_equity": 5150.0,
                "daily_pnl": 50.0,
                "cumulative_pnl": 150.0,
                "high_water_mark": 5150.0,
                "drawdown_pct": 0.0,
            },
        ]
        
        render_equity_chart(equity_data)
        
        # Check plotly chart was called
        mock_streamlit.plotly_chart.assert_called_once()
        
        # Check metrics were displayed
        assert mock_streamlit.metric.call_count == 4


class TestRenderTradeFeed:
    """Tests for render_trade_feed function."""
    
    def test_renders_empty_trade_feed(self, mock_streamlit):
        """Test that empty trade feed shows info message."""
        render_trade_feed([])
        
        mock_streamlit.info.assert_called_with("No trades available")
        mock_streamlit.dataframe.assert_not_called()
    
    def test_renders_trade_feed_with_data(self, mock_streamlit):
        """Test that trade feed renders with data."""
        trades = [
            {
                "trade_time": datetime(2024, 1, 1, 12, 0, 0),
                "city_code": "NYC",
                "ticker": "HIGHNYC-01JAN24",
                "side": "yes",
                "quantity": 10,
                "price": 45,
                "realized_pnl": 25.0,
            },
            {
                "trade_time": datetime(2024, 1, 1, 13, 0, 0),
                "city_code": "CHI",
                "ticker": "HIGHCHI-01JAN24",
                "side": "no",
                "quantity": 5,
                "price": 52,
                "realized_pnl": -10.0,
            },
            {
                "trade_time": datetime(2024, 1, 1, 14, 0, 0),
                "city_code": "LAX",
                "ticker": "HIGHLAX-01JAN24",
                "side": "yes",
                "quantity": 8,
                "price": 48,
                "realized_pnl": None,
            },
        ]
        
        render_trade_feed(trades)
        
        # Check dataframe was called
        mock_streamlit.dataframe.assert_called_once()


class TestRenderPerformanceHeatmap:
    """Tests for render_performance_heatmap function."""
    
    def test_renders_empty_heatmap(self, mock_streamlit):
        """Test that empty heatmap shows info message."""
        render_performance_heatmap([])
        
        mock_streamlit.info.assert_called_with("No performance data available")
        mock_streamlit.plotly_chart.assert_not_called()
    
    def test_renders_heatmap_with_data(self, mock_streamlit):
        """Test that heatmap renders with data."""
        city_metrics = [
            {
                "city_code": "NYC",
                "win_rate": 65.0,
                "net_pnl": 250.0,
                "trade_count": 10,
            },
            {
                "city_code": "CHI",
                "win_rate": 55.0,
                "net_pnl": -50.0,
                "trade_count": 8,
            },
            {
                "city_code": "LAX",
                "win_rate": 60.0,
                "net_pnl": 0.0,
                "trade_count": 5,
            },
        ]
        
        render_performance_heatmap(city_metrics)
        
        # Check plotly chart was called
        mock_streamlit.plotly_chart.assert_called_once()
        
        # Check subheader was called
        mock_streamlit.subheader.assert_called_with("City Breakdown")
        
        # Check write was called for each city
        assert mock_streamlit.write.call_count >= 3


class TestRenderHealthIndicator:
    """Tests for render_health_indicator function."""
    
    def test_renders_health_indicator_unknown(self, mock_streamlit):
        """Test that unknown health status is rendered."""
        render_health_indicator(None)
        
        mock_streamlit.write.assert_called_with("🔘 Unknown")
    
    def test_renders_health_indicator_healthy(self, mock_streamlit):
        """Test that healthy status is rendered."""
        health_data = {"overall_status": "healthy"}
        
        render_health_indicator(health_data)
        
        mock_streamlit.success.assert_called_with("✅ System Healthy")
    
    def test_renders_health_indicator_degraded(self, mock_streamlit):
        """Test that degraded status is rendered."""
        health_data = {"overall_status": "degraded"}
        
        render_health_indicator(health_data)
        
        mock_streamlit.warning.assert_called_with("⚠️ Degraded")
    
    def test_renders_health_indicator_unhealthy(self, mock_streamlit):
        """Test that unhealthy status is rendered."""
        health_data = {"overall_status": "unhealthy"}
        
        render_health_indicator(health_data)
        
        mock_streamlit.error.assert_called_with("❌ Unhealthy")
    
    def test_renders_health_indicator_unknown_status(self, mock_streamlit):
        """Test that unknown status value is handled."""
        health_data = {"overall_status": "invalid"}
        
        render_health_indicator(health_data)
        
        mock_streamlit.info.assert_called_with("🔘 Unknown")
