"""Main Streamlit dashboard application.

MilkBot Climate Exchange Dashboard
"""

import base64
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import streamlit as st

# Page config must be first Streamlit command
st.set_page_config(
    page_title="MilkBot Climate Exchange",
    page_icon="🌤️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =============================================================================
# GLOBAL STYLES - Including LOCAL Freckle Face font
# =============================================================================

# Load Freckle Face font as base64 for bulletproof local hosting
def get_font_base64():
    font_path = Path("src/dashboard/assets/fonts/freckle-face.woff2")
    if font_path.exists():
        with open(font_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

FRECKLE_FACE_B64 = get_font_base64()

# Inject all global styles in ONE block
st.markdown(f"""
<style>
/* ============================================
   LOCAL FONT: Freckle Face (bulletproof)
   ============================================ */
@font-face {{
    font-family: 'Freckle Face';
    src: url(data:font/woff2;base64,{FRECKLE_FACE_B64}) format('woff2');
    font-weight: normal;
    font-style: normal;
    font-display: swap;
}}

/* Other fonts via Google */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ============================================
   BASE STYLES
   ============================================ */
* {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}

/* Hide Streamlit chrome */
#MainMenu {{visibility: hidden;}}
header {{visibility: hidden;}}
footer {{visibility: hidden;}}

/* Dark background everywhere */
[data-testid="stAppViewContainer"], .stApp {{
    background-color: #0a0a0a !important;
}}

/* Container */
.block-container {{
    padding-top: 10px !important;
    padding-bottom: 0 !important;
    max-width: 1400px !important;
}}

/* ============================================
   HEADER STYLES - Very compact
   ============================================ */
.header-text-block {{
    text-align: center;
    padding: 10px 0;
}}

.milkbot-title {{
    font-family: 'Freckle Face', cursive !important;
    font-size: 56px;
    color: #94a3b8;
    line-height: 1;
    margin: 0 0 4px 0;
}}

.climate-title {{
    font-family: 'Inter', sans-serif !important;
    font-size: 42px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 2px;
    background: linear-gradient(90deg, #00ffc8, #00d9ff, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
    margin: 0 0 6px 0;
}}

.tagline {{
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 22px;
    font-style: italic;
    font-weight: 600;
    color: #1e90ff;
    line-height: 1.2;
    margin: 8px 0 0 0;
}}

/* ============================================
   TABS
   ============================================ */
.stTabs [data-baseweb="tab-list"] {{
    justify-content: center;
    gap: 6px;
    background-color: transparent;
    flex-wrap: wrap;
}}
.stTabs [data-baseweb="tab"] {{
    height: 40px;
    padding: 8px 16px;
    background-color: #1a1f2e;
    border-radius: 6px 6px 0 0;
    font-size: 13px !important;
    font-weight: 500;
}}

/* ============================================
   CITY CARDS
   ============================================ */
.city-card {{
    background-color: #1a1f2e;
    border: 1px solid #2d333b;
    border-radius: 8px;
    padding: 12px 8px;
    text-align: center;
    margin-bottom: 6px;
}}
.city-name-large {{
    color: #fafafa;
    font-size: 15px;
    margin: 0 0 4px 0;
    font-weight: 700;
}}
.city-temp {{
    font-size: 28px;
    font-weight: 700;
    color: #00ffc8;
    margin-bottom: 4px;
}}
.city-card .stat-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3px 4px;
}}
.city-card .stat-label {{
    color: #6b7280;
    font-size: 9px;
    text-transform: uppercase;
}}
.city-card .stat-value {{
    color: #00d9ff;
    font-size: 13px;
    font-weight: 600;
}}
.city-card .signal-buy {{ color: #06b6d4; }}
.city-card .signal-sell {{ color: #f97316; }}
.city-card .signal-hold {{ color: #6b7280; }}
.city-card .spread-tight {{ color: #10b981; }}
.city-card .spread-medium {{ color: #f59e0b; }}
.city-card .spread-wide {{ color: #ef4444; }}
.city-card .volume-value {{ color: #a78bfa; }}
.city-card .pnl-positive {{ color: #10b981; }}
.city-card .pnl-negative {{ color: #ef4444; }}

/* ============================================
   BREAKDOWN CARDS
   ============================================ */
.breakdown-card {{
    background: #1a1f2e;
    padding: 12px 8px;
    border-radius: 6px;
    text-align: center;
    border: 1px solid #2d333b;
    margin-bottom: 6px;
}}
.breakdown-card .city-code {{
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 6px;
}}

/* ============================================
   MOBILE RESPONSIVE
   ============================================ */
@media (max-width: 768px) {{
    .block-container {{
        padding: 6px 10px !important;
    }}
    
    /* Center logo on mobile */
    [data-testid="column"]:first-child {{
        display: flex;
        justify-content: center;
    }}
    
    .milkbot-title {{
        font-size: 40px;
    }}
    .climate-title {{
        font-size: 28px;
        letter-spacing: 1px;
    }}
    .tagline {{
        font-size: 15px;
    }}
    
    /* Tabs wrap into rows */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 4px;
    }}
    .stTabs [data-baseweb="tab"] {{
        padding: 6px 10px;
        font-size: 11px !important;
        flex: 1 1 45%;
        min-width: 0;
    }}
    
    /* Larger body text on mobile (+2pt equivalent) */
    .city-card, .breakdown-card, [data-testid="stMarkdown"] p {{
        font-size: 14px !important;
    }}
    .city-name-large {{
        font-size: 14px;
    }}
    .city-temp {{
        font-size: 24px;
    }}
    .city-card .stat-label {{
        font-size: 10px;
    }}
    .city-card .stat-value {{
        font-size: 14px;
    }}
}}
</style>
""", unsafe_allow_html=True)

# Import components after styles
from src.dashboard.components import (
    render_city_grid,
    render_city_performance_table,
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
    """Render COMPACT header: logo left, text center, empty right."""
    # 3-column layout
    left_col, center_col, right_col = st.columns([1, 2, 1])
    
    with left_col:
        logo_path = Path("src/dashboard/assets/milkbot-logo.png")
        if logo_path.exists():
            st.image(str(logo_path), width=180)
    
    with center_col:
        # Use CSS classes for fonts
        st.markdown("""
        <div class="header-text-block">
            <div class="milkbot-title">MilkBot</div>
            <div class="climate-title">CLIMATE EXCHANGE</div>
            <div class="tagline">"Glitch The System. Burn The Map."</div>
        </div>
        """, unsafe_allow_html=True)
    
    with right_col:
        st.write("")


def render_status_row() -> None:
    """Render status row SEPARATE from header."""
    import pytz
    
    nyc_tz = pytz.timezone("America/New_York")
    nyc_now = datetime.now(pytz.utc).astimezone(nyc_tz)
    tz_abbrev = "EST" if nyc_now.dst() == timedelta(0) else "EDT"
    current_time = nyc_now.strftime(f"%-I:%M %p {tz_abbrev}")
    
    # Status row - clearly separate, single line, one rule below
    st.markdown(f"""
    <div style="text-align: center; padding: 8px 0; font-family: 'JetBrains Mono', monospace; font-size: 15px; margin-top: 4px;">
        <span style="color: #f97316; font-weight: 600;">🛡️ 60-MIN DELAY • ANTI-FRONTRUN</span>
        <span style="color: #4b5563; margin: 0 16px;">|</span>
        <span style="color: #10b981; font-weight: 600;">● LIVE • {current_time}</span>
    </div>
    <div style="height: 1px; background: #2d333b; margin: 6px 0 12px 0;"></div>
    """, unsafe_allow_html=True)


def render_stats_strip(data_provider: DashboardDataProvider) -> None:
    """Render compact stats strip under status row."""
    equity_data = data_provider.get_equity_curve()
    city_metrics = data_provider.get_city_metrics()
    
    starting_bankroll = int(os.environ.get("BANKROLL", "1500"))
    if equity_data:
        current_equity = equity_data[-1].get("ending_equity", starting_bankroll)
        daily_pnl = equity_data[-1].get("daily_pnl", 0)
        total_pnl = equity_data[-1].get("cumulative_pnl", 0)
    else:
        current_equity = starting_bankroll
        daily_pnl = 0
        total_pnl = 0
    
    if city_metrics:
        total_trades = sum(m.get("trade_count", 0) for m in city_metrics)
        total_wins = sum(m.get("win_count", 0) for m in city_metrics)
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        best_city = max(city_metrics, key=lambda x: x.get("net_pnl", 0))
        worst_city = min(city_metrics, key=lambda x: x.get("net_pnl", 0))
    else:
        overall_win_rate = 0
        best_city = {"city_code": "N/A", "net_pnl": 0}
        worst_city = {"city_code": "N/A", "net_pnl": 0}
    
    # 5 compact stats
    cols = st.columns(5)
    
    # Card styling - darker than main cards
    card_css = "background:#0d1117;padding:10px 6px;border-radius:6px;text-align:center;border:1px solid #1a1f2e;"
    label_css = "color:#6b7280;font-size:9px;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px;"
    value_css = "font-size:18px;font-weight:700;line-height:1.1;"
    sub_css = "font-size:10px;margin-top:2px;"
    
    with cols[0]:
        pnl_color = "#10b981" if daily_pnl >= 0 else "#ef4444"
        st.markdown(f"""
        <div style="{card_css}">
            <div style="{label_css}">Portfolio</div>
            <div style="{value_css}color:#00d9ff;">${current_equity:,.0f}</div>
            <div style="{sub_css}color:{pnl_color};">{daily_pnl:+,.0f} today</div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[1]:
        total_color = "#10b981" if total_pnl >= 0 else "#ef4444"
        st.markdown(f"""
        <div style="{card_css}">
            <div style="{label_css}">Total P&L</div>
            <div style="{value_css}color:{total_color};">${total_pnl:+,.0f}</div>
            <div style="{sub_css}color:#6b7280;">Since Jan 31</div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[2]:
        st.markdown(f"""
        <div style="{card_css}">
            <div style="{label_css}">Win Rate</div>
            <div style="{value_css}color:#00d9ff;">{overall_win_rate:.1f}%</div>
            <div style="{sub_css}color:#6b7280;">{total_trades} trades</div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[3]:
        best_pnl = best_city.get("net_pnl", 0)
        st.markdown(f"""
        <div style="{card_css}">
            <div style="{label_css}">Top City</div>
            <div style="{value_css}color:#00d9ff;">{best_city.get("city_code", "N/A")}</div>
            <div style="{sub_css}color:#10b981;">${best_pnl:+,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[4]:
        worst_pnl = worst_city.get("net_pnl", 0)
        worst_color = "#ef4444" if worst_pnl < 0 else "#6b7280"
        st.markdown(f"""
        <div style="{card_css}">
            <div style="{label_css}">Worst City</div>
            <div style="{value_css}color:#00d9ff;">{worst_city.get("city_code", "N/A")}</div>
            <div style="{sub_css}color:{worst_color};">${worst_pnl:+,.0f}</div>
        </div>
        """, unsafe_allow_html=True)


def render_footer() -> None:
    """Render footer."""
    st.markdown("""
    <div style="text-align: center; padding: 20px 0 16px 0; margin-top: 32px; border-top: 1px solid #2d333b;">
        <p style="font-size: 13px; color: #6b7280; margin: 0;">Built by MilkBot • Owned by Binary Rogue, LLC</p>
    </div>
    """, unsafe_allow_html=True)


def render_main_content() -> None:
    """Render main dashboard content."""
    data_provider = get_data_provider()

    render_stats_strip(data_provider)
    
    st.markdown("<div style='height:10px;'></div>", unsafe_allow_html=True)

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
    """Render city markets tab."""
    st.markdown('<h2 style="font-size:24px;font-weight:700;color:#fafafa;text-align:center;margin:12px 0 16px 0;">10-City Market Overview</h2>', unsafe_allow_html=True)
    city_data = data_provider.get_city_market_data()
    render_city_grid(city_data)


def render_performance_tab(data_provider: DashboardDataProvider) -> None:
    """Render performance tab with LARGE metric cards."""
    city_metrics = data_provider.get_city_metrics()
    
    # Get equity data
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    equity_data = data_provider.get_equity_curve(start_date, end_date)
    
    starting_bankroll = int(os.environ.get("BANKROLL", "1500"))
    if equity_data:
        start_equity = equity_data[0].get("ending_equity", starting_bankroll) - equity_data[0].get("daily_pnl", 0)
        end_equity = equity_data[-1].get("ending_equity", starting_bankroll)
        total_return = equity_data[-1].get("cumulative_pnl", 0)
        max_dd = max(p.get("drawdown_pct", 0) for p in equity_data)
    else:
        start_equity = starting_bankroll
        end_equity = starting_bankroll
        total_return = 0
        max_dd = 0
    
    # ==========================================================================
    # PERFORMANCE METRIC CARDS - DOUBLED FONT SIZE
    # ==========================================================================
    st.markdown('<h3 style="font-size:20px;font-weight:600;color:#fafafa;margin:0 0 12px 0;">Performance Summary</h3>', unsafe_allow_html=True)
    
    metric_cols = st.columns(4)
    
    # Card style with LARGE numbers (32px - doubled from ~16px)
    card_bg = "#1a1f2e"
    card_border = "#2d333b"
    label_size = "12px"
    value_size = "32px"  # DOUBLED
    
    with metric_cols[0]:
        st.markdown(f"""
        <div style="background:{card_bg};padding:16px;border-radius:8px;text-align:center;border:1px solid {card_border};">
            <div style="color:#6b7280;font-size:{label_size};text-transform:uppercase;margin-bottom:6px;">Starting Equity</div>
            <div style="color:#00d9ff;font-size:{value_size};font-weight:700;">${start_equity:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with metric_cols[1]:
        st.markdown(f"""
        <div style="background:{card_bg};padding:16px;border-radius:8px;text-align:center;border:1px solid {card_border};">
            <div style="color:#6b7280;font-size:{label_size};text-transform:uppercase;margin-bottom:6px;">Current Equity</div>
            <div style="color:#00d9ff;font-size:{value_size};font-weight:700;">${end_equity:,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with metric_cols[2]:
        return_color = "#10b981" if total_return >= 0 else "#ef4444"
        st.markdown(f"""
        <div style="background:{card_bg};padding:16px;border-radius:8px;text-align:center;border:1px solid {card_border};">
            <div style="color:#6b7280;font-size:{label_size};text-transform:uppercase;margin-bottom:6px;">Total Return</div>
            <div style="color:{return_color};font-size:{value_size};font-weight:700;">${total_return:+,.0f}</div>
        </div>
        """, unsafe_allow_html=True)
    
    with metric_cols[3]:
        dd_color = "#ef4444" if max_dd > 5 else "#f59e0b" if max_dd > 2 else "#10b981"
        st.markdown(f"""
        <div style="background:{card_bg};padding:16px;border-radius:8px;text-align:center;border:1px solid {card_border};">
            <div style="color:#6b7280;font-size:{label_size};text-transform:uppercase;margin-bottom:6px;">Max Drawdown</div>
            <div style="color:{dd_color};font-size:{value_size};font-weight:700;">{max_dd:.1f}%</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    
    # Equity Curve
    st.markdown('<h3 style="font-size:20px;font-weight:600;color:#fafafa;margin:0 0 10px 0;">Equity Curve</h3>', unsafe_allow_html=True)
    
    range_options = {"1 Day": 1, "7 Days": 7, "1 Month": 30, "All Time": 365}
    selected_range = st.selectbox("Time Range", options=list(range_options.keys()), index=2, key="perf_range")
    days = range_options[selected_range]
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    equity_data = data_provider.get_equity_curve(start_date, end_date)
    render_equity_chart(equity_data)
    
    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    
    # City Performance Matrix
    st.markdown('<h3 style="font-size:20px;font-weight:600;color:#fafafa;margin:0 0 10px 0;">City Performance Matrix</h3>', unsafe_allow_html=True)
    render_performance_heatmap(city_metrics)
    
    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    
    # Detailed Table (always visible)
    st.markdown('<h3 style="font-size:20px;font-weight:600;color:#fafafa;margin:0 0 10px 0;">Detailed City Performance</h3>', unsafe_allow_html=True)
    render_city_performance_table(city_metrics)


def render_trade_feed_tab(data_provider: DashboardDataProvider) -> None:
    """Render trade feed tab."""
    st.markdown('<h3 style="font-size:20px;font-weight:600;color:#fafafa;margin:0 0 8px 0;">Public Trade Feed</h3>', unsafe_allow_html=True)
    st.info("⏱️ Trades are delayed by 60 minutes for transparency")

    cities = ["All Cities"] + data_provider.get_city_codes()
    selected_city = st.selectbox("Filter by City", cities)
    city_filter = None if selected_city == "All Cities" else selected_city

    trades = data_provider.get_public_trades(city_code=city_filter, limit=100)
    render_trade_feed(trades)


def render_health_tab(data_provider: DashboardDataProvider) -> None:
    """Render system health tab."""
    st.markdown('<h3 style="font-size:20px;font-weight:600;color:#fafafa;margin:0 0 10px 0;">System Health Status</h3>', unsafe_allow_html=True)

    health_data = data_provider.get_health_status()

    if health_data:
        overall = health_data.get("overall_status", "unknown")
        overall_icon = "✅" if overall == "healthy" else "⚠️" if overall == "degraded" else "❌"
        overall_color = "#10b981" if overall == "healthy" else "#f59e0b" if overall == "degraded" else "#ef4444"
        
        st.markdown(f"""
        <div style="background:#1a1f2e;padding:16px;border-radius:8px;text-align:center;margin-bottom:16px;border:1px solid #2d333b;">
            <div style="font-size:36px;margin-bottom:4px;">{overall_icon}</div>
            <div style="font-size:20px;font-weight:700;color:{overall_color};text-transform:uppercase;">{overall}</div>
            <div style="color:#6b7280;font-size:12px;margin-top:4px;">System Status</div>
        </div>
        """, unsafe_allow_html=True)

        summary = health_data.get("summary", {})
        cols = st.columns(3)
        
        metrics = [
            ("Healthy", summary.get("total_healthy", 0), "#10b981"),
            ("Degraded", summary.get("total_degraded", 0), "#f59e0b"),
            ("Unhealthy", summary.get("total_unhealthy", 0), "#ef4444"),
        ]
        
        for i, (label, value, color) in enumerate(metrics):
            with cols[i]:
                st.markdown(f"""
                <div style="background:#1a1f2e;padding:14px;border-radius:6px;text-align:center;border:1px solid #2d333b;">
                    <div style="font-size:24px;font-weight:700;color:{color};">{value}</div>
                    <div style="color:#6b7280;font-size:12px;margin-top:4px;">{label}</div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        st.markdown('<h4 style="font-size:16px;font-weight:600;color:#fafafa;margin:0 0 10px 0;">Component Details</h4>', unsafe_allow_html=True)

        components = health_data.get("components", [])
        if components:
            comp_cols = st.columns(2)
            for idx, comp in enumerate(components):
                status = comp.get("status", "unknown")
                icon = "✅" if status == "healthy" else "⚠️" if status == "degraded" else "❌"
                color = "#10b981" if status == "healthy" else "#f59e0b" if status == "degraded" else "#ef4444"
                
                with comp_cols[idx % 2]:
                    latency = comp.get("latency_ms")
                    latency_text = f"{latency:.0f}ms" if latency else "N/A"
                    error_rate = comp.get("error_rate")
                    error_text = f"{error_rate*100:.1f}%" if error_rate else "0%"
                    
                    st.markdown(f"""
                    <div style="background:#1a1f2e;padding:12px;border-radius:6px;margin-bottom:8px;border:1px solid #2d333b;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                            <span style="font-size:14px;font-weight:600;color:#fff;">{icon} {comp.get('name', 'Unknown')}</span>
                            <span style="color:{color};font-weight:600;text-transform:uppercase;font-size:12px;">{status}</span>
                        </div>
                        <div style="display:flex;gap:16px;color:#9ca3af;font-size:11px;">
                            <span>Latency: <b style="color:#00d9ff;">{latency_text}</b></span>
                            <span>Error Rate: <b style="color:#00d9ff;">{error_text}</b></span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No component data available")
    else:
        st.warning("Unable to fetch health status")


def main() -> None:
    """Main dashboard entry point."""
    # Render in order: Header -> Status Row -> Content -> Footer
    render_header()
    render_status_row()
    render_main_content()
    render_footer()

    # Sidebar
    with st.sidebar:
        st.header("Settings")
        if st.button("Refresh Now"):
            st.rerun()
        st.divider()
        st.caption("MilkBot Climate Exchange v1.0")
        st.caption("Data delayed 60 minutes")


if __name__ == "__main__":
    main()
