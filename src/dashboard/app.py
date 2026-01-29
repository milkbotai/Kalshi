"""Main Streamlit dashboard application.

Public dashboard for weather trading platform showing:
- 10-city grid with market data
- Delayed trade feed (60-minute delay)
- Equity curve chart
- City performance heatmap
- System health indicator
"""

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any

import streamlit as st

# Page config must be first Streamlit command
st.set_page_config(
    page_title="Weather Trading Dashboard",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Import components after page config
from src.dashboard.components import (
    render_city_grid,
    render_equity_chart,
    render_health_indicator,
    render_performance_heatmap,
    render_trade_feed,
)
from src.dashboard.data import DashboardDataProvider


def get_data_provider() -> DashboardDataProvider:
    """Get or create data provider from session state."""
    if "data_provider" not in st.session_state:
        st.session_state.data_provider = DashboardDataProvider()
    return st.session_state.data_provider


def render_header() -> None:
    """Render dashboard header with title and health indicator."""
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        st.title("🌤️ Weather Trading Dashboard")
        st.caption("Live market data and performance metrics")

    with col2:
        # Last update time
        st.metric(
            "Last Updated",
            datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        )

    with col3:
        # Health indicator
        data_provider = get_data_provider()
        health_data = data_provider.get_health_status()
        render_health_indicator(health_data)


def render_main_content() -> None:
    """Render main dashboard content."""
    data_provider = get_data_provider()

    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 City Markets",
        "📈 Performance",
        "💰 Trade Feed",
        "🏥 System Health",
    ])

    with tab1:
        render_city_markets_tab(data_provider)

    with tab2:
        render_performance_tab(data_provider)

    with tab3:
        render_trade_feed_tab(data_provider)

    with tab4:
        render_health_tab(data_provider)


def render_city_markets_tab(data_provider: DashboardDataProvider) -> None:
    """Render city markets tab with 10-city grid."""
    st.subheader("10-City Market Overview")

    # Get city data
    city_data = data_provider.get_city_market_data()

    # Render grid
    render_city_grid(city_data)


def render_performance_tab(data_provider: DashboardDataProvider) -> None:
    """Render performance tab with equity curve and heatmap."""
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Portfolio Equity Curve")

        # Date range selector
        range_options = {
            "1 Week": 7,
            "1 Month": 30,
            "3 Months": 90,
            "All Time": 365,
        }
        selected_range = st.selectbox(
            "Time Range",
            options=list(range_options.keys()),
            index=1,
        )
        days = range_options[selected_range]

        # Get equity curve data
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        equity_data = data_provider.get_equity_curve(start_date, end_date)

        # Render chart
        render_equity_chart(equity_data)

    with col2:
        st.subheader("City Performance Heatmap")

        # Get city metrics
        city_metrics = data_provider.get_city_metrics()

        # Render heatmap
        render_performance_heatmap(city_metrics)


def render_trade_feed_tab(data_provider: DashboardDataProvider) -> None:
    """Render trade feed tab with delayed trades."""
    st.subheader("Public Trade Feed")
    st.info("⏱️ Trades are delayed by 60 minutes for transparency")

    # City filter
    cities = ["All Cities"] + data_provider.get_city_codes()
    selected_city = st.selectbox("Filter by City", cities)

    city_filter = None if selected_city == "All Cities" else selected_city

    # Get trades
    trades = data_provider.get_public_trades(city_code=city_filter, limit=100)

    # Render feed
    render_trade_feed(trades)


def render_health_tab(data_provider: DashboardDataProvider) -> None:
    """Render system health tab with detailed status."""
    st.subheader("System Health Status")

    health_data = data_provider.get_health_status()

    if health_data:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Overall Status",
                health_data.get("overall_status", "Unknown").upper(),
            )

        summary = health_data.get("summary", {})

        with col2:
            st.metric("Healthy", summary.get("total_healthy", 0))

        with col3:
            st.metric("Degraded", summary.get("total_degraded", 0))

        with col4:
            st.metric("Unhealthy", summary.get("total_unhealthy", 0))

        # Component details
        st.subheader("Component Details")

        components = health_data.get("components", [])
        if components:
            for comp in components:
                status = comp.get("status", "unknown")
                icon = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"

                with st.expander(f"{icon} {comp.get('name', 'Unknown')}", expanded=status != "healthy"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Status:** {status}")
                        st.write(f"**Last Check:** {comp.get('last_check', 'N/A')}")
                    with col2:
                        latency = comp.get("latency_ms")
                        if latency:
                            st.write(f"**Latency:** {latency:.1f}ms")
                        error_rate = comp.get("error_rate")
                        if error_rate:
                            st.write(f"**Error Rate:** {error_rate*100:.2f}%")
                    if comp.get("message"):
                        st.write(f"**Message:** {comp.get('message')}")
        else:
            st.info("No component data available")
    else:
        st.warning("Unable to fetch health status")


def main() -> None:
    """Main dashboard entry point."""
    # Custom CSS for styling
    st.markdown("""
        <style>
        .stMetric {
            background-color: #f0f2f6;
            padding: 10px;
            border-radius: 5px;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            padding-left: 20px;
            padding-right: 20px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Render header
    render_header()

    st.divider()

    # Render main content
    render_main_content()

    # Auto-refresh every 5 seconds
    # Note: In production, use st.rerun() with a timer or websockets
    # For now, we use a simple approach
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = True

    # Sidebar for settings
    with st.sidebar:
        st.header("Settings")
        st.session_state.auto_refresh = st.checkbox(
            "Auto-refresh (5s)",
            value=st.session_state.auto_refresh,
        )

        if st.button("Refresh Now"):
            st.rerun()

        st.divider()
        st.caption("Weather Trading Platform v1.0")
        st.caption("Data delayed 60 minutes")


if __name__ == "__main__":
    main()
