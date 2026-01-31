"""Tests for dashboard app module."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.dashboard.app import (
    get_data_provider,
    render_header,
    render_main_content,
    render_city_markets_tab,
    render_performance_tab,
    render_trade_feed_tab,
    render_health_tab,
    main,
)
from src.dashboard.data import DashboardDataProvider, CityMarketData


class MockSessionState:
    """Custom mock for Streamlit session state that supports both dict and attribute access."""
    
    def __init__(self):
        self._data = {}
    
    def __getitem__(self, key):
        return self._data.get(key)
    
    def __setitem__(self, key, value):
        self._data[key] = value
    
    def __contains__(self, key):
        return key in self._data
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        if name in self._data:
            return self._data[name]
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    
    def __setattr__(self, name, value):
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            self._data[name] = value


@pytest.fixture
def mock_data_provider():
    """Create a mock data provider."""
    provider = Mock(spec=DashboardDataProvider)
    
    # Mock city market data
    provider.get_city_market_data.return_value = [
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
    ]
    
    # Mock city codes
    provider.get_city_codes.return_value = ["NYC", "CHI", "LAX", "MIA", "SEA"]
    
    # Mock equity curve
    provider.get_equity_curve.return_value = [
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
    
    # Mock city metrics
    provider.get_city_metrics.return_value = [
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
    ]
    
    # Mock public trades
    provider.get_public_trades.return_value = [
        {
            "trade_time": datetime.now(timezone.utc),
            "city_code": "NYC",
            "ticker": "HIGHNYC-01JAN24",
            "side": "yes",
            "quantity": 10,
            "price": 45,
            "realized_pnl": 25.0,
        },
    ]
    
    # Mock health status
    provider.get_health_status.return_value = {
        "overall_status": "healthy",
        "summary": {
            "total_healthy": 5,
            "total_degraded": 1,
            "total_unhealthy": 0,
        },
        "components": [
            {
                "name": "Database",
                "status": "healthy",
                "last_check": "2024-01-01T12:00:00Z",
                "latency_ms": 10.5,
                "error_rate": 0.0,
                "message": None,
            },
            {
                "name": "Kalshi API",
                "status": "degraded",
                "last_check": "2024-01-01T12:00:00Z",
                "latency_ms": 150.0,
                "error_rate": 0.05,
                "message": "High latency detected",
            },
        ],
    }
    
    return provider


@pytest.fixture
def mock_streamlit():
    """Mock streamlit session state and functions."""
    with patch("src.dashboard.app.st") as mock_st:
        # Use custom session state class
        mock_st.session_state = MockSessionState()
        
        # Mock UI elements
        mock_st.title = Mock()
        mock_st.caption = Mock()
        mock_st.metric = Mock()
        mock_st.subheader = Mock()
        mock_st.info = Mock()
        mock_st.warning = Mock()
        mock_st.divider = Mock()
        mock_st.markdown = Mock()
        mock_st.write = Mock()
        mock_st.header = Mock()
        mock_st.button = Mock(return_value=False)
        mock_st.checkbox = Mock(return_value=True)
        mock_st.selectbox = Mock(return_value="1 Month")
        mock_st.rerun = Mock()
        
        # Mock columns - return context manager mocks
        def create_column_mock():
            col = Mock()
            col.__enter__ = Mock(return_value=col)
            col.__exit__ = Mock(return_value=False)
            return col
        
        def columns_side_effect(spec):
            if isinstance(spec, int):
                return [create_column_mock() for _ in range(spec)]
            elif isinstance(spec, list):
                return [create_column_mock() for _ in range(len(spec))]
            return [create_column_mock(), create_column_mock()]
        
        mock_st.columns = Mock(side_effect=columns_side_effect)
        
        # Mock tabs
        def create_tab_mock():
            tab = Mock()
            tab.__enter__ = Mock(return_value=tab)
            tab.__exit__ = Mock(return_value=False)
            return tab
        
        mock_st.tabs = Mock(return_value=[create_tab_mock() for _ in range(4)])
        
        # Mock sidebar as a context manager
        # Inside `with st.sidebar:`, calls go to st.header, st.checkbox, etc. (not sidebar.header)
        mock_sidebar = Mock()
        mock_sidebar.__enter__ = Mock(return_value=mock_sidebar)
        mock_sidebar.__exit__ = Mock(return_value=False)
        mock_st.sidebar = mock_sidebar
        
        # Mock expander
        mock_expander = Mock()
        mock_expander.__enter__ = Mock(return_value=mock_expander)
        mock_expander.__exit__ = Mock(return_value=False)
        mock_expander.write = Mock()
        mock_st.expander = Mock(return_value=mock_expander)
        
        yield mock_st


class TestGetDataProvider:
    """Tests for get_data_provider function."""
    
    def test_creates_new_provider_if_not_in_session(self, mock_streamlit):
        """Test that a new provider is created if not in session state."""
        provider = get_data_provider()
        
        assert provider is not None
        assert "data_provider" in mock_streamlit.session_state
    
    def test_returns_existing_provider_from_session(self, mock_streamlit, mock_data_provider):
        """Test that existing provider is returned from session state."""
        # Manually set the provider in session state
        mock_streamlit.session_state.data_provider = mock_data_provider
        
        provider = get_data_provider()
        
        assert provider is mock_data_provider


class TestRenderHeader:
    """Tests for render_header function."""
    
    @patch("src.dashboard.app.get_data_provider")
    @patch("src.dashboard.app.render_health_indicator")
    def test_renders_header_components(self, mock_render_health, mock_get_provider, mock_streamlit, mock_data_provider):
        """Test that header renders all components."""
        mock_get_provider.return_value = mock_data_provider
        
        render_header()
        
        # Check title was called
        mock_streamlit.title.assert_called_once()
        assert "Weather Trading Dashboard" in str(mock_streamlit.title.call_args)
        
        # Check caption was called
        mock_streamlit.caption.assert_called()
        
        # Check metric was called for last updated
        mock_streamlit.metric.assert_called()
        
        # Check health indicator was rendered
        mock_render_health.assert_called_once()


class TestRenderCityMarketsTab:
    """Tests for render_city_markets_tab function."""
    
    @patch("src.dashboard.app.render_city_grid")
    def test_renders_city_markets(self, mock_render_grid, mock_streamlit, mock_data_provider):
        """Test that city markets tab renders correctly."""
        render_city_markets_tab(mock_data_provider)
        
        # Check subheader was called
        mock_streamlit.subheader.assert_called_with("10-City Market Overview")
        
        # Check data was fetched
        mock_data_provider.get_city_market_data.assert_called_once()
        
        # Check grid was rendered
        mock_render_grid.assert_called_once()


class TestRenderPerformanceTab:
    """Tests for render_performance_tab function."""
    
    @patch("src.dashboard.app.render_equity_chart")
    @patch("src.dashboard.app.render_performance_heatmap")
    def test_renders_performance_tab(self, mock_render_heatmap, mock_render_chart, mock_streamlit, mock_data_provider):
        """Test that performance tab renders correctly."""
        mock_streamlit.selectbox.return_value = "1 Month"
        
        render_performance_tab(mock_data_provider)
        
        # Check subheaders were called
        assert mock_streamlit.subheader.call_count >= 2
        
        # Check selectbox was called for time range
        mock_streamlit.selectbox.assert_called()
        
        # Check equity curve was fetched and rendered
        mock_data_provider.get_equity_curve.assert_called_once()
        mock_render_chart.assert_called_once()
        
        # Check city metrics were fetched and rendered
        mock_data_provider.get_city_metrics.assert_called_once()
        mock_render_heatmap.assert_called_once()
    
    @patch("src.dashboard.app.render_equity_chart")
    @patch("src.dashboard.app.render_performance_heatmap")
    def test_handles_different_time_ranges(self, mock_render_heatmap, mock_render_chart, mock_streamlit, mock_data_provider):
        """Test that different time ranges are handled correctly."""
        for time_range in ["1 Week", "3 Months", "All Time"]:
            mock_streamlit.selectbox.return_value = time_range
            mock_data_provider.reset_mock()
            
            render_performance_tab(mock_data_provider)
            
            # Check equity curve was fetched
            mock_data_provider.get_equity_curve.assert_called_once()


class TestRenderTradeFeedTab:
    """Tests for render_trade_feed_tab function."""
    
    @patch("src.dashboard.app.render_trade_feed")
    def test_renders_trade_feed_all_cities(self, mock_render_feed, mock_streamlit, mock_data_provider):
        """Test that trade feed renders for all cities."""
        mock_streamlit.selectbox.return_value = "All Cities"
        
        render_trade_feed_tab(mock_data_provider)
        
        # Check subheader and info were called
        mock_streamlit.subheader.assert_called_with("Public Trade Feed")
        mock_streamlit.info.assert_called()
        
        # Check city codes were fetched
        mock_data_provider.get_city_codes.assert_called_once()
        
        # Check trades were fetched with no city filter
        mock_data_provider.get_public_trades.assert_called_with(city_code=None, limit=100)
        
        # Check feed was rendered
        mock_render_feed.assert_called_once()
    
    @patch("src.dashboard.app.render_trade_feed")
    def test_renders_trade_feed_filtered_city(self, mock_render_feed, mock_streamlit, mock_data_provider):
        """Test that trade feed renders for specific city."""
        mock_streamlit.selectbox.return_value = "NYC"
        
        render_trade_feed_tab(mock_data_provider)
        
        # Check trades were fetched with city filter
        mock_data_provider.get_public_trades.assert_called_with(city_code="NYC", limit=100)


class TestRenderHealthTab:
    """Tests for render_health_tab function."""
    
    def test_renders_health_tab_with_data(self, mock_streamlit, mock_data_provider):
        """Test that health tab renders with data."""
        render_health_tab(mock_data_provider)
        
        # Check subheader was called
        mock_streamlit.subheader.assert_called()
        
        # Check health status was fetched
        mock_data_provider.get_health_status.assert_called_once()
        
        # Check metrics were displayed
        assert mock_streamlit.metric.call_count >= 4
        
        # Check expander was used for components
        mock_streamlit.expander.assert_called()
    
    def test_renders_health_tab_without_data(self, mock_streamlit, mock_data_provider):
        """Test that health tab handles missing data."""
        mock_data_provider.get_health_status.return_value = None
        
        render_health_tab(mock_data_provider)
        
        # Check warning was displayed
        mock_streamlit.warning.assert_called_with("Unable to fetch health status")
    
    def test_renders_health_tab_no_components(self, mock_streamlit, mock_data_provider):
        """Test that health tab handles missing components."""
        mock_data_provider.get_health_status.return_value = {
            "overall_status": "healthy",
            "summary": {"total_healthy": 0, "total_degraded": 0, "total_unhealthy": 0},
            "components": [],
        }
        
        render_health_tab(mock_data_provider)
        
        # Check info was displayed
        mock_streamlit.info.assert_called_with("No component data available")


class TestRenderMainContent:
    """Tests for render_main_content function."""
    
    @patch("src.dashboard.app.render_city_markets_tab")
    @patch("src.dashboard.app.render_performance_tab")
    @patch("src.dashboard.app.render_trade_feed_tab")
    @patch("src.dashboard.app.render_health_tab")
    @patch("src.dashboard.app.get_data_provider")
    def test_renders_all_tabs(
        self,
        mock_get_provider,
        mock_render_health,
        mock_render_trades,
        mock_render_performance,
        mock_render_markets,
        mock_streamlit,
        mock_data_provider,
    ):
        """Test that main content renders all tabs."""
        mock_get_provider.return_value = mock_data_provider
        
        render_main_content()
        
        # Check tabs were created
        mock_streamlit.tabs.assert_called_once()
        
        # Check all tab render functions were called
        mock_render_markets.assert_called_once()
        mock_render_performance.assert_called_once()
        mock_render_trades.assert_called_once()
        mock_render_health.assert_called_once()


class TestMain:
    """Tests for main function."""
    
    @patch("src.dashboard.app.render_main_content")
    @patch("src.dashboard.app.render_header")
    def test_main_renders_dashboard(self, mock_render_header, mock_render_content, mock_streamlit):
        """Test that main function renders the dashboard."""
        main()
        
        # Check markdown for custom CSS was called
        mock_streamlit.markdown.assert_called()
        
        # Check header was rendered
        mock_render_header.assert_called_once()
        
        # Check divider was added
        mock_streamlit.divider.assert_called()
        
        # Check main content was rendered
        mock_render_content.assert_called_once()
    
    @patch("src.dashboard.app.render_main_content")
    @patch("src.dashboard.app.render_header")
    def test_main_renders_sidebar(self, mock_render_header, mock_render_content, mock_streamlit):
        """Test that main function renders the sidebar."""
        main()
        
        # Verify sidebar context manager was used
        mock_streamlit.sidebar.__enter__.assert_called_once()
        mock_streamlit.sidebar.__exit__.assert_called_once()
        
        # Inside `with st.sidebar:`, calls go to st.header, st.checkbox, st.button
        # (not sidebar.header, etc.)
        mock_streamlit.header.assert_called_with("Settings")
        mock_streamlit.checkbox.assert_called()
        mock_streamlit.button.assert_called_with("Refresh Now")
        mock_streamlit.caption.assert_called()
    
    @patch("src.dashboard.app.render_main_content")
    @patch("src.dashboard.app.render_header")
    def test_main_handles_refresh_button(self, mock_render_header, mock_render_content, mock_streamlit):
        """Test that refresh button triggers rerun."""
        # Configure button to return True (simulating a click)
        mock_streamlit.button.return_value = True
        
        main()
        
        # Check rerun was called when button returns True
        mock_streamlit.rerun.assert_called_once()
    
    @patch("src.dashboard.app.render_main_content")
    @patch("src.dashboard.app.render_header")
    def test_main_initializes_auto_refresh(self, mock_render_header, mock_render_content, mock_streamlit):
        """Test that auto_refresh is initialized in session state."""
        main()
        
        # Check auto_refresh was set in session state
        assert "auto_refresh" in mock_streamlit.session_state
    
    @patch("src.dashboard.app.render_main_content")
    @patch("src.dashboard.app.render_header")
    def test_main_no_rerun_when_button_not_clicked(self, mock_render_header, mock_render_content, mock_streamlit):
        """Test that rerun is not called when button is not clicked."""
        # Button returns False (not clicked)
        mock_streamlit.button.return_value = False
        
        main()
        
        # Check rerun was NOT called
        mock_streamlit.rerun.assert_not_called()
