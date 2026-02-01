"""Dashboard UI components.

Reusable Streamlit components for the dashboard including:
- City grid layout
- Equity curve chart
- Trade feed table
- Performance heatmap
- Health indicator
"""

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.data import CityMarketData


def render_city_grid(city_data: list[CityMarketData]) -> None:
    """Render 10-city grid layout.

    Displays market data for all cities in a responsive grid.

    Args:
        city_data: List of CityMarketData objects
    """
    if not city_data:
        st.warning("No city data available")
        return

    # Create 2 rows of 5 cities each
    row1_cities = city_data[:5]
    row2_cities = city_data[5:10]

    # Row 1
    cols1 = st.columns(5)
    for i, city in enumerate(row1_cities):
        with cols1[i]:
            render_city_card(city)

    # Row 2
    cols2 = st.columns(5)
    for i, city in enumerate(row2_cities):
        with cols2[i]:
            render_city_card(city)


def render_city_card(city: CityMarketData) -> None:
    """Render a single city card with centered grid layout.

    Args:
        city: CityMarketData for the city
    """
    from datetime import datetime, timezone, timedelta
    
    # Spread value and color class
    spread_val = city.spread if city.spread is not None else 0
    spread_text = f"{spread_val}¢" if city.spread is not None else "—"
    # Spread color classes: tight (0-3), medium (4-6), wide (7+)
    if spread_val <= 3:
        spread_class = "spread-tight"
    elif spread_val <= 6:
        spread_class = "spread-medium"
    else:
        spread_class = "spread-wide"
    
    volume_text = f"{city.volume:,}" if city.volume is not None else "—"
    
    # Signal with color class
    signal = city.last_signal if city.last_signal else "HOLD"
    signal_class = "signal-buy" if signal == "BUY" else "signal-sell" if signal == "SELL" else "signal-hold"
    
    # Temperature display
    if city.current_temp is not None:
        temp_text = f"{city.current_temp:.0f}°F"
    else:
        temp_text = "—"
    
    # Weather freshness indicator
    stale_warning = ""
    if city.weather_stale:
        stale_warning = '<div style="color: #ef4444; font-size: 13px; margin-top: 0.25rem;">⚠️ STALE</div>'
    elif city.weather_updated_at:
        age_min = int((datetime.now(timezone.utc) - city.weather_updated_at).total_seconds() / 60)
        stale_warning = f'<div style="color: #9ca3af; font-size: 13px; margin-top: 0.25rem;">{age_min}m ago</div>'
    
    # Format bid/ask separately for flexbox display
    bid_val = f"{city.yes_bid}¢" if city.yes_bid is not None else "—"
    ask_val = f"{city.yes_ask}¢" if city.yes_ask is not None else "—"
    
    # Win rate and P&L
    win_rate_text = f"{city.win_rate:.0f}%" if city.win_rate is not None else "—"
    pnl_val = city.net_pnl if city.net_pnl is not None else 0
    pnl_text = f"${pnl_val:+,.0f}" if city.net_pnl is not None else "—"
    pnl_class = "pnl-positive" if pnl_val > 0 else "pnl-negative" if pnl_val < 0 else ""
    
    # Render compact city card - full name only, no 3-letter code
    card_html = f"""
    <div class="city-card">
        <div class="city-name-large">{city.city_name}</div>
        <div class="city-temp">{temp_text}</div>
        {stale_warning}
        <div style="margin-top: 8px;" class="stat-grid">
            <div class="stat-item">
                <div class="stat-label">Bid/Ask</div>
                <div class="stat-value" style="display: flex; gap: 4px; justify-content: center; font-size: 13px;">
                    <span>{bid_val}</span>
                    <span style="color: #6b7280;">/</span>
                    <span>{ask_val}</span>
                </div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Spread</div>
                <div class="stat-value {spread_class}">{spread_text}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Vol</div>
                <div class="stat-value volume-value">{volume_text}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Signal</div>
                <div class="stat-value {signal_class}">{signal}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Win%</div>
                <div class="stat-value">{win_rate_text}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">P&L</div>
                <div class="stat-value {pnl_class}">{pnl_text}</div>
            </div>
        </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def render_equity_chart(equity_data: list[dict[str, Any]]) -> None:
    """Render equity curve chart with Plotly.

    Args:
        equity_data: List of equity curve points
    """
    if not equity_data:
        st.info("No equity data available")
        return

    # Convert to DataFrame
    df = pd.DataFrame(equity_data)
    df["date"] = pd.to_datetime(df["date"])

    # Create figure with secondary y-axis
    fig = go.Figure()

    # Equity line
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["ending_equity"],
            name="Equity",
            line=dict(color="blue", width=2),
            hovertemplate="Date: %{x}<br>Equity: $%{y:,.2f}<extra></extra>",
        )
    )

    # High water mark line
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["high_water_mark"],
            name="High Water Mark",
            line=dict(color="green", width=1, dash="dash"),
            hovertemplate="Date: %{x}<br>HWM: $%{y:,.2f}<extra></extra>",
        )
    )

    # Drawdown fill area
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["ending_equity"],
            fill="tonexty",
            fillcolor="rgba(255, 0, 0, 0.1)",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # Layout
    fig.update_layout(
        title=None,
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=0, r=0, t=30, b=0),
    )

    st.plotly_chart(fig, width='stretch')

    # Summary metrics below chart
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        start_equity = equity_data[0].get("ending_equity", 0) - equity_data[0].get("daily_pnl", 0)
        st.metric("Starting Equity", f"${start_equity:,.2f}")

    with col2:
        end_equity = equity_data[-1].get("ending_equity", 0)
        st.metric("Current Equity", f"${end_equity:,.2f}")

    with col3:
        total_return = equity_data[-1].get("cumulative_pnl", 0)
        st.metric("Total Return", f"${total_return:,.2f}")

    with col4:
        max_dd = max(p.get("drawdown_pct", 0) for p in equity_data)
        st.metric("Max Drawdown", f"{max_dd:.1f}%")


def render_trade_feed(trades: list[dict[str, Any]]) -> None:
    """Render public trade feed using native Streamlit components.

    Args:
        trades: List of trade dictionaries
    """
    import pytz
    import re
    
    if not trades:
        st.info("No trades available")
        return

    # Convert to DataFrame
    df = pd.DataFrame(trades)

    # Convert to NYC timezone
    nyc_tz = pytz.timezone("America/New_York")
    df["trade_time"] = pd.to_datetime(df["trade_time"])
    if df["trade_time"].dt.tz is None:
        df["trade_time"] = df["trade_time"].dt.tz_localize("UTC")
    df["trade_time"] = df["trade_time"].dt.tz_convert(nyc_tz)
    df["time_fmt"] = df["trade_time"].dt.strftime("%m/%d %-I:%M%p")

    # Ticker formatting
    def format_ticker(ticker: str) -> str:
        match = re.match(r'HIGH(\w{3})-(\d{2})(\w{3})(\d{2})-T(\d+)', ticker)
        if match:
            city, day, month, year, threshold = match.groups()
            return f"{day} {month} T{threshold}"
        return ticker
    
    df["market"] = df["ticker"].apply(format_ticker)
    
    # Format side with color emoji
    df["side_fmt"] = df["side"].apply(lambda x: f"🟦 {x.upper()}" if x == "yes" else f"🟧 {x.upper()}")
    
    # Format P&L with color and sign
    def format_pnl_text(val):
        if val is None or pd.isna(val):
            return "—"
        elif val > 0:
            return f"+${val:.2f}"
        elif val < 0:
            return f"${val:.2f}"
        else:
            return "$0.00"
    
    df["pnl_fmt"] = df["realized_pnl"].apply(format_pnl_text)
    df["price_fmt"] = df["price"].apply(lambda x: f"{x}¢")

    # Render as individual trade cards for better mobile support
    st.markdown("### Recent Trades")
    
    for idx, row in df.head(20).iterrows():
        # Determine colors
        side_color = "#06b6d4" if row["side"] == "yes" else "#f97316"
        pnl_val = row.get("realized_pnl")
        if pnl_val is None or pd.isna(pnl_val):
            pnl_color = "#6b7280"
        elif pnl_val > 0:
            pnl_color = "#10b981"
        elif pnl_val < 0:
            pnl_color = "#ef4444"
        else:
            pnl_color = "#6b7280"
        
        # Alternating row colors for readability
        bg_color = "rgba(255,255,255,0.02)" if idx % 2 == 0 else "rgba(255,255,255,0.05)"
        
        # Create trade card
        with st.container():
            cols = st.columns([2, 2, 3, 2, 1, 1, 2])
            
            with cols[0]:
                st.markdown(f'<div style="color: #6b7280; font-size: 13px; padding: 8px 4px; background: {bg_color}; border-radius: 4px;">{row["time_fmt"]}</div>', unsafe_allow_html=True)
            
            with cols[1]:
                st.markdown(f'<div style="color: #00d9ff; font-weight: 600; font-size: 14px; padding: 8px 4px; background: {bg_color}; border-radius: 4px;">{row["city_code"]}</div>', unsafe_allow_html=True)
            
            with cols[2]:
                st.markdown(f'<div style="color: #9ca3af; font-family: monospace; font-size: 13px; padding: 8px 4px; background: {bg_color}; border-radius: 4px;">{row["market"]}</div>', unsafe_allow_html=True)
            
            with cols[3]:
                st.markdown(f'<div style="color: {side_color}; font-weight: 600; padding: 8px 4px; background: {bg_color}; border-radius: 4px;">{row["side_fmt"]}</div>', unsafe_allow_html=True)
            
            with cols[4]:
                st.markdown(f'<div style="color: #e5e7eb; padding: 8px 4px; background: {bg_color}; border-radius: 4px; text-align: center;">{row["quantity"]}</div>', unsafe_allow_html=True)
            
            with cols[5]:
                st.markdown(f'<div style="color: #e5e7eb; padding: 8px 4px; background: {bg_color}; border-radius: 4px; text-align: center;">{row["price_fmt"]}</div>', unsafe_allow_html=True)
            
            with cols[6]:
                st.markdown(f'<div style="color: {pnl_color}; font-weight: 600; padding: 8px 4px; background: {bg_color}; border-radius: 4px; text-align: right;">{row["pnl_fmt"]}</div>', unsafe_allow_html=True)


def render_performance_heatmap(city_metrics: list[dict[str, Any]]) -> None:
    """Render city performance scatter plot showing Win Rate vs P&L.

    Args:
        city_metrics: List of city metrics dictionaries
    """
    if not city_metrics:
        st.info("No performance data available")
        return

    # Convert to DataFrame
    df = pd.DataFrame(city_metrics)

    # Extract data for scatter plot
    cities = df['city_code'].tolist()
    win_rates = df['win_rate'].tolist()
    pnls = df['net_pnl'].tolist()

    # Color code based on performance quadrant
    colors = []
    for wr, pnl in zip(win_rates, pnls):
        if wr >= 50 and pnl >= 0:
            colors.append('#10b981')  # Green: High win + profit (best)
        elif wr < 50 and pnl < 0:
            colors.append('#ef4444')  # Red: Low win + loss (worst)
        elif wr >= 50 and pnl < 0:
            colors.append('#f59e0b')  # Amber: High win but loss (unlucky)
        else:
            colors.append('#7dd3fc')  # Cyan: Low win but profit (lucky)

    # Create scatter plot
    fig = go.Figure()

    # Add scatter points
    fig.add_trace(go.Scatter(
        x=win_rates,
        y=pnls,
        mode='markers+text',
        marker=dict(
            size=25,
            color=colors,
            line=dict(width=2, color='rgba(255,255,255,0.8)'),
            symbol='circle'
        ),
        text=cities,
        textposition='top center',
        textfont=dict(size=13, color='white', family='monospace', weight='bold'),
        hovertemplate=(
            '<b>%{text}</b><br>' +
            'Win Rate: %{x:.1f}%<br>' +
            'P&L: $%{y:,.2f}<br>' +
            '<extra></extra>'
        ),
        showlegend=False
    ))

    # Add quadrant reference lines
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)", line_width=1)
    fig.add_vline(x=50, line_dash="dash", line_color="rgba(255,255,255,0.2)", line_width=1)

    # Calculate ranges for annotations
    max_pnl = max(pnls) if pnls else 1000
    min_pnl = min(pnls) if pnls else -1000
    pnl_range = max_pnl - min_pnl

    fig.update_layout(
        title={
            'text': 'City Performance Matrix',
            'font': {'size': 24, 'color': 'white'},
            'x': 0.5,
            'xanchor': 'center'
        },
        height=600,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(26,26,26,1)',
        font=dict(color='white', size=14),
        xaxis=dict(
            title='Win Rate (%)',
            range=[30, 80],
            gridcolor='rgba(255,255,255,0.05)',
            tickfont=dict(size=12)
        ),
        yaxis=dict(
            title='Net P&L ($)',
            gridcolor='rgba(255,255,255,0.05)',
            zeroline=True,
            zerolinecolor='rgba(255,255,255,0.2)',
            zerolinewidth=2,
            tickfont=dict(size=12)
        ),
        annotations=[
            # Top-right: Best performers
            dict(
                x=70,
                y=max_pnl - (pnl_range * 0.15) if pnl_range > 0 else 100,
                text="🎯 High Win + Profit",
                showarrow=False,
                font=dict(color='#10b981', size=12, family='monospace'),
                bgcolor='rgba(16, 185, 129, 0.15)',
                borderpad=5
            ),
            # Bottom-left: Worst performers
            dict(
                x=40,
                y=min_pnl + (pnl_range * 0.15) if pnl_range > 0 else -100,
                text="⚠️ Low Win + Loss",
                showarrow=False,
                font=dict(color='#ef4444', size=12, family='monospace'),
                bgcolor='rgba(239, 68, 68, 0.15)',
                borderpad=5
            ),
        ],
        margin=dict(l=60, r=40, t=80, b=60)
    )

    st.plotly_chart(fig, width='stretch')
    
    # Add legend explanation
    st.markdown("""
    <div style="text-align: center; margin-top: -20px; padding: 15px; color: #9ca3af; font-size: 13px; background: rgba(26,26,26,0.5); border-radius: 8px;">
        <b>Performance Quadrants:</b>
        <span style="color: #10b981; font-weight: bold;">● Top-Right = Best</span> |
        <span style="color: #ef4444; font-weight: bold;">● Bottom-Left = Worst</span> |
        <span style="color: #7dd3fc; font-weight: bold;">● Top-Left = Lucky</span> |
        <span style="color: #f59e0b; font-weight: bold;">● Bottom-Right = Unlucky</span>
    </div>
    """, unsafe_allow_html=True)

    # City Breakdown - Clean grid with all 4 required data points per city
    st.markdown('<h4 style="font-size: 18px; font-weight: 600; color: #fafafa; margin: 24px 0 12px 0;">City Breakdown</h4>', unsafe_allow_html=True)

    # Sort by net P&L descending
    df_sorted = df.sort_values("net_pnl", ascending=False)
    
    # Create rows of 5 cities each (for desktop), wraps on mobile
    cities_per_row = 5
    city_list = list(df_sorted.iterrows())
    
    for i in range(0, len(city_list), cities_per_row):
        row_cities = city_list[i:i+cities_per_row]
        cols = st.columns(len(row_cities))
        
        for idx, (_, row) in enumerate(row_cities):
            with cols[idx]:
                pnl = row["net_pnl"]
                pnl_color = "#10b981" if pnl > 0 else "#ef4444" if pnl < 0 else "#6b7280"
                win_rate = row["win_rate"]
                wr_color = "#10b981" if win_rate >= 55 else "#f59e0b" if win_rate >= 45 else "#ef4444"
                
                # Card with: City Code, Win Rate, P&L, Trades
                st.markdown(f"""
                <div style="background: #1a1f2e; padding: 14px 10px; border-radius: 8px; text-align: center; border: 1px solid #2d333b;">
                    <div style="font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 10px;">{row['city_code']}</div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <div>
                            <div style="color: #6b7280; font-size: 10px; text-transform: uppercase;">Win Rate</div>
                            <div style="color: {wr_color}; font-size: 16px; font-weight: 600;">{win_rate:.1f}%</div>
                        </div>
                        <div>
                            <div style="color: #6b7280; font-size: 10px; text-transform: uppercase;">P&L</div>
                            <div style="color: {pnl_color}; font-size: 16px; font-weight: 600;">${pnl:+,.0f}</div>
                        </div>
                    </div>
                    <div style="color: #6b7280; font-size: 11px; margin-top: 10px;">{row['trade_count']} trades</div>
                </div>
                """, unsafe_allow_html=True)


def render_city_performance_table(city_metrics: list[dict[str, Any]]) -> None:
    """Render detailed city performance table.
    
    Uses CSS grid for clean layout. Same architectural pattern as Trade Feed.
    ONE OPTIONAL IMPROVEMENT: Added subtle row hover highlight for scanability.

    Args:
        city_metrics: List of city metrics dictionaries
    """
    if not city_metrics:
        st.info("No performance data available")
        return

    # Convert to DataFrame and sort by P&L
    df = pd.DataFrame(city_metrics)
    df = df.sort_values("net_pnl", ascending=False)
    
    # Inject hover styles (ONE OPTIONAL IMPROVEMENT: row hover for scanability)
    st.markdown("""
    <style>
    .perf-row:hover {
        background: #1a2332 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Header row
    st.markdown("""
    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1.2fr 1.3fr 1.3fr 1fr; gap: 8px; padding: 12px 8px; border-bottom: 1px solid #2d333b; margin-bottom: 4px;">
        <div style="color: #6b7280; font-size: 11px; font-weight: 600; text-transform: uppercase;">City</div>
        <div style="color: #6b7280; font-size: 11px; font-weight: 600; text-transform: uppercase;">Trades</div>
        <div style="color: #6b7280; font-size: 11px; font-weight: 600; text-transform: uppercase;">Wins</div>
        <div style="color: #6b7280; font-size: 11px; font-weight: 600; text-transform: uppercase;">Losses</div>
        <div style="color: #6b7280; font-size: 11px; font-weight: 600; text-transform: uppercase;">Win Rate</div>
        <div style="color: #6b7280; font-size: 11px; font-weight: 600; text-transform: uppercase;">Net P&L</div>
        <div style="color: #6b7280; font-size: 11px; font-weight: 600; text-transform: uppercase;">Gross P&L</div>
        <div style="color: #6b7280; font-size: 11px; font-weight: 600; text-transform: uppercase;">Fees</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Data rows
    for idx, (_, row) in enumerate(df.iterrows()):
        # Alternating row background for readability
        bg_color = "#0f1318" if idx % 2 == 0 else "#0a0d10"
        
        # P&L colors
        net_pnl = row["net_pnl"]
        net_color = "#10b981" if net_pnl > 0 else "#ef4444" if net_pnl < 0 else "#6b7280"
        
        # Win rate color
        win_rate = row["win_rate"]
        wr_color = "#10b981" if win_rate >= 55 else "#00d9ff" if win_rate >= 45 else "#f59e0b"
        
        st.markdown(f"""
        <div class="perf-row" style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1.2fr 1.3fr 1.3fr 1fr; gap: 8px; padding: 10px 8px; background: {bg_color}; border-radius: 4px; margin-bottom: 2px; transition: background 0.15s ease;">
            <div style="color: #fafafa; font-weight: 600; font-size: 14px;">{row["city_code"]}</div>
            <div style="color: #9ca3af; font-size: 14px;">{row["trade_count"]}</div>
            <div style="color: #10b981; font-size: 14px;">{row["win_count"]}</div>
            <div style="color: #ef4444; font-size: 14px;">{row["loss_count"]}</div>
            <div style="color: {wr_color}; font-size: 14px; font-weight: 500;">{win_rate:.1f}%</div>
            <div style="color: {net_color}; font-weight: 600; font-size: 14px;">${net_pnl:+,.2f}</div>
            <div style="color: #9ca3af; font-size: 14px;">${row["gross_pnl"]:,.2f}</div>
            <div style="color: #6b7280; font-size: 14px;">${row["fees"]:.2f}</div>
        </div>
        """, unsafe_allow_html=True)


def render_health_indicator(health_data: dict[str, Any] | None) -> None:
    """Render compact health indicator for header.

    Args:
        health_data: Health status dictionary
    """
    if not health_data:
        st.write("🔘 Unknown")
        return

    overall_status = health_data.get("overall_status", "unknown")

    if overall_status == "healthy":
        st.success("✅ System Healthy")
    elif overall_status == "degraded":
        st.warning("⚠️ Degraded")
    elif overall_status == "unhealthy":
        st.error("❌ Unhealthy")
    else:
        st.info("🔘 Unknown")
