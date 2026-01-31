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
    """Render a single city card with centered 2x2 grid layout.

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
    
    # Render custom HTML card with sophisticated color palette
    card_html = f"""
    <div class="city-card">
        <h3>{city.city_code}</h3>
        <div class="city-name">{city.city_name}</div>
        <div class="city-temp">{temp_text}</div>
        {stale_warning}
        <div style="margin-top: 1rem;" class="stat-grid">
            <div class="stat-item">
                <div class="stat-label">Bid / Ask</div>
                <div class="stat-value" style="display: flex; gap: 8px; justify-content: center; align-items: center;">
                    <span>{bid_val}</span>
                    <span style="color: #9ca3af;">/</span>
                    <span>{ask_val}</span>
                </div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Spread</div>
                <div class="stat-value {spread_class}">{spread_text}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Volume</div>
                <div class="stat-value volume-value">{volume_text}</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">Signal</div>
                <div class="stat-value {signal_class}">{signal}</div>
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
    """Render public trade feed table.

    Args:
        trades: List of trade dictionaries
    """
    if not trades:
        st.info("No trades available")
        return

    # Convert to DataFrame for display
    df = pd.DataFrame(trades)

    # Format columns
    df["trade_time"] = pd.to_datetime(df["trade_time"]).dt.strftime("%Y-%m-%d %H:%M")
    df["price"] = df["price"].apply(lambda x: f"{x}¢")

    # P&L formatting
    def format_pnl(val: float | None) -> str:
        if val is None:
            return "—"
        color = "green" if val > 0 else "red" if val < 0 else "gray"
        return f"${val:+.2f}"

    df["realized_pnl"] = df["realized_pnl"].apply(format_pnl)

    # Select and rename columns for display
    display_cols = {
        "trade_time": "Time",
        "city_code": "City",
        "ticker": "Ticker",
        "side": "Side",
        "quantity": "Qty",
        "price": "Price",
        "realized_pnl": "P&L",
    }

    df_display = df[list(display_cols.keys())].rename(columns=display_cols)

    # Display as table
    st.dataframe(
        df_display,
        width='stretch',
        hide_index=True,
        height=400,
    )


def render_performance_heatmap(city_metrics: list[dict[str, Any]]) -> None:
    """Render city performance heatmap.

    Args:
        city_metrics: List of city metrics dictionaries
    """
    if not city_metrics:
        st.info("No performance data available")
        return

    # Convert to DataFrame
    df = pd.DataFrame(city_metrics)

    # Create heatmap data
    heatmap_data = df.set_index("city_code")[["win_rate", "net_pnl"]].T

    # Win rate heatmap
    fig = px.imshow(
        heatmap_data,
        labels=dict(x="City", y="Metric", color="Value"),
        x=heatmap_data.columns,
        y=["Win Rate (%)", "Net P&L ($)"],
        color_continuous_scale="RdYlGn",
        aspect="auto",
    )

    fig.update_layout(
        title=None,
        margin=dict(l=0, r=0, t=30, b=0),
    )

    st.plotly_chart(fig, width='stretch')

    # Summary table
    st.subheader("City Breakdown")

    # Sort by net P&L
    df_sorted = df.sort_values("net_pnl", ascending=False)

    for _, row in df_sorted.iterrows():
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.write(f"**{row['city_code']}**")

        with col2:
            st.write(f"Win Rate: {row['win_rate']:.1f}%")

        with col3:
            pnl = row["net_pnl"]
            pnl_color = "green" if pnl > 0 else "red" if pnl < 0 else "gray"
            st.markdown(f"P&L: <span style='color:{pnl_color}'>${pnl:,.2f}</span>", unsafe_allow_html=True)

        with col4:
            st.write(f"Trades: {row['trade_count']}")


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
