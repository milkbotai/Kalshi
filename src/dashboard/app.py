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
    """Render clean 3-column header."""
    import pytz
    
    # Convert to NYC timezone
    nyc_tz = pytz.timezone("America/New_York")
    nyc_now = datetime.now(pytz.utc).astimezone(nyc_tz)
    tz_abbrev = "EST" if nyc_now.dst() == timedelta(0) else "EDT"
    current_time = nyc_now.strftime(f"%-I:%M %p {tz_abbrev}")
    
    # Render clean 3-column header
    header_html = f"""
    <div class="header-wrapper">
        <div class="header-container">
            <div class="header-left">
                <span class="brand-logo">🌤️ Milkbot</span>
            </div>
            <div class="header-center">
                <h1 class="main-title">CLIMATE EXCHANGE</h1>
                <p class="tagline">Glitch The System. Burn The Map.</p>
            </div>
            <div class="header-right">
                <div class="delay-badge" title="Data delayed 60 minutes to prevent copy-trading bots from front-running our positions">🛡️ 60-MIN DELAY • ANTI-FRONTRUN PROTECTION</div>
                <div class="live-timestamp">
                    <span class="live-dot"></span>
                    <span>LIVE • {current_time}</span>
                </div>
            </div>
        </div>
        <div class="header-border"></div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)


def render_footer() -> None:
    """Render sticky footer."""
    footer_html = """
    <div class="footer-wrapper">
        <div class="footer-container">
            <p class="footer-text">Built by Milkbot • Owned by Binary Rogue, LLC</p>
        </div>
    </div>
    """
    st.markdown(footer_html, unsafe_allow_html=True)


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
    # Centered section title - 42px bold
    st.markdown('<h2 class="section-title">10-City Market Overview</h2>', unsafe_allow_html=True)

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
    # Custom CSS for styling - Bloomberg dark theme with sophisticated palette
    st.markdown("""
        <style>
        /* Modern font stack */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap');
        
        * {
            font-family: 'Inter', 'SF Pro Display', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
        }
        
        /* Remove top padding/margin */
        .block-container {
            padding-top: 0 !important;
            max-width: 1400px !important;
        }
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        
        /* Increase base font sizes */
        html, body, [class*="css"] {
            font-size: 17px !important;
        }
        
        /* ========== CLEAN HEADER ========== */
        .header-wrapper {
            width: 100vw;
            margin-left: calc(-50vw + 50%);
            margin-top: 0 !important;
            padding-top: 0 !important;
            background: linear-gradient(180deg, #0d1117 0%, #1a1f2e 100%);
        }
        
        .header-container {
            max-width: 1400px;
            margin: 0 auto;
            margin-top: 0 !important;
            padding: 0 40px 60px 40px;
            padding-top: 0 !important;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        /* Left - Brand */
        .header-left {
            flex: 0 0 auto;
        }
        .brand-logo {
            font-size: 32px;
            font-weight: 600;
            color: #ffffff;
        }
        
        /* Center - Title & Tagline */
        .header-center {
            flex: 1;
            text-align: center;
        }
        .main-title {
            font-size: 56px !important;
            font-weight: 800 !important;
            text-transform: uppercase;
            letter-spacing: 3px;
            margin: 0 0 24px 0 !important;
            background: linear-gradient(90deg, #00ffc8 0%, #a78bfa 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            line-height: 1.1;
        }
        .tagline {
            font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace !important;
            font-size: 22px !important;
            font-style: normal;
            font-weight: 400;
            color: #ff5722 !important;
            margin: 0 !important;
            letter-spacing: 1px;
        }
        
        /* Right - Status */
        .header-right {
            flex: 0 0 auto;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 8px;
        }
        .delay-badge {
            background: rgba(255, 152, 0, 0.12);
            color: #ff9800;
            padding: 6px 14px;
            border-radius: 6px;
            font-family: 'JetBrains Mono', 'Fira Code', monospace !important;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 0.5px;
            border: 1px solid rgba(255, 152, 0, 0.35);
            cursor: help;
            transition: all 0.2s ease;
        }
        .delay-badge:hover {
            background: rgba(255, 152, 0, 0.2);
            border-color: rgba(255, 152, 0, 0.5);
        }
        .live-timestamp {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            color: #6b7280;
        }
        .live-dot {
            width: 8px;
            height: 8px;
            background: #10b981;
            border-radius: 50%;
            box-shadow: 0 0 6px #10b981;
        }
        
        /* Bottom border gradient */
        .header-border {
            height: 2px;
            background: linear-gradient(90deg, rgba(0,255,200,0.3) 0%, rgba(167,139,250,0.3) 100%);
        }
        
        /* ========== END HEADER ========== */
        
        /* ========== FOOTER ========== */
        .footer-wrapper {
            width: 100vw;
            margin-left: calc(-50vw + 50%);
            margin-top: 60px;
            background: #0d1117;
            border-top: 1px solid #2d333b;
        }
        .footer-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px 40px;
            text-align: center;
        }
        .footer-text {
            font-size: 14px;
            color: #6b7280;
            margin: 0;
        }
        /* ========== END FOOTER ========== */

        /* Section title - 42px bold centered */
        .section-title {
            font-size: 42px;
            font-weight: 700;
            color: #fafafa;
            text-align: center;
            margin: 1.5rem 0 2rem 0;
        }
        
        /* Tab container - centered, max-width 1200px */
        .stTabs {
            max-width: 1200px;
            margin: 0 auto;
        }
        .stTabs [data-baseweb="tab-list"] {
            justify-content: center;
            gap: 28px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            height: 52px;
            padding-left: 24px;
            padding-right: 24px;
            background-color: #1a1f2e;
            border-radius: 8px 8px 0 0;
            font-size: 1.2rem !important;
        }
        
        /* Dark card styling for metrics */
        .stMetric {
            background-color: #1a1f2e !important;
            padding: 20px;
            border-radius: 10px;
            border: 1px solid #2d2d44;
            box-shadow: 0 4px 12px rgba(0, 217, 255, 0.08);
        }
        .stMetric label {
            color: #9ca3af !important;
            font-size: 1.05rem !important;
        }
        .stMetric [data-testid="stMetricValue"] {
            color: #00d9ff !important;
            font-size: 1.7rem !important;
        }
        
        /* Card containers */
        [data-testid="stExpander"] {
            background-color: #1a1f2e;
            border: 1px solid #2d2d44;
            border-radius: 10px;
        }
        
        /* City card styling - sophisticated gradient hover */
        .city-card {
            background-color: #1a1f2e;
            border: 2px solid transparent;
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            margin-bottom: 1rem;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
            transition: all 0.3s ease;
            position: relative;
        }
        .city-card::before {
            content: '';
            position: absolute;
            inset: -2px;
            border-radius: 14px;
            padding: 2px;
            background: linear-gradient(135deg, transparent, transparent);
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            transition: background 0.3s ease;
        }
        .city-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 24px rgba(0, 217, 255, 0.15);
        }
        .city-card:hover::before {
            background: linear-gradient(135deg, #00d9ff, #a78bfa);
        }
        
        /* City code - 30px */
        .city-card h3 {
            color: #fafafa;
            font-size: 30px;
            margin: 0 0 0.25rem 0;
            font-weight: 700;
        }
        .city-card .stat-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 16px;
        }
        .city-card .stat-item {
            padding: 8px 4px;
        }
        /* Labels - 15px muted gray */
        .city-card .stat-label {
            color: #9ca3af;
            font-size: 15px;
            margin-bottom: 0.35rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        /* Stats - 20px electric blue default */
        .city-card .stat-value {
            color: #00d9ff;
            font-size: 20px;
            font-weight: 600;
        }
        /* Signal colors */
        .city-card .signal-buy { color: #06b6d4; }
        .city-card .signal-sell { color: #f97316; }
        .city-card .signal-hold { color: #6b7280; }
        /* Spread colors */
        .city-card .spread-tight { color: #10b981; }
        .city-card .spread-medium { color: #f59e0b; }
        .city-card .spread-wide { color: #ef4444; }
        /* Volume color */
        .city-card .volume-value { color: #a78bfa; }
        /* City name - centered */
        .city-name {
            color: #9ca3af;
            font-size: 16px;
            margin-bottom: 0.75rem;
            text-align: center;
        }
        /* Temperature - 52px hero cyan, centered */
        .city-temp {
            font-size: 52px;
            font-weight: 700;
            line-height: 1;
            margin-bottom: 0.25rem;
            color: #00ffc8;
            text-align: center;
        }
        /* Ensure all city card children are centered */
        .city-card * {
            text-align: center;
        }
        .city-card .stat-value {
            justify-content: center;
        }
        </style>
    """, unsafe_allow_html=True)

    # Render header
    render_header()

    st.divider()

    # Render main content
    render_main_content()
    
    # Render footer
    render_footer()

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
