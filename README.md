# Binary Rogue: MilkBot Climate Exchange

> *"Every normal man must be tempted, at times, to spit on his hands, hoist the black flag, and begin slitting throats."*
> — H.L. Mencken

---

## The Black Flag Philosophy

**Binary Rogue** is a multi-agent AI company building autonomous systems that operate at the edge of chaos. **MilkBot** is our first hire—an AI trading agent specializing in climate derivatives on [Kalshi](https://kalshi.com).

While traditional traders chase earnings reports and Fed minutes, MilkBot reads the sky.

This isn't a toy. MilkBot is a fully autonomous trading engine that:
- Ingests real-time NWS weather data across 10 major U.S. cities
- Calculates probability distributions for daily high temperatures
- Identifies mispriced YES/NO contracts on Kalshi's prediction markets
- Executes trades with surgical precision and ironclad risk management

**The edge?** Weather forecasts are public. Market prices are public. But the gap between what the atmosphere *will* do and what the crowd *thinks* it will do—that's where alpha lives.

MilkBot doesn't predict the weather. It predicts the prediction.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Infrastructure** | Ubuntu 24.04 VPS, Nginx reverse proxy, Cloudflare DNS/SSL |
| **Backend** | Python 3.12, async trading loop, PostgreSQL persistence |
| **Dashboard** | Streamlit with custom dark theme ("Binary Rogue" aesthetic) |
| **AI Cluster** | OpenRouter API (Claude Sonnet 4 for analysis and explanation) |
| **Weather Data** | National Weather Service (NWS) API, real-time observations |
| **Exchange** | Kalshi REST API v2 with RSA key authentication |

### The 5-Model Scoring System

Our proprietary signal generation combines:
1. **NWS Forecast Model** — Point estimates from government meteorologists
2. **Historical Variance Model** — City-specific standard deviations
3. **Market Sentiment Model** — Implied probabilities from current prices
4. **Edge Calculator** — Fair value vs. market price differential
5. **Uncertainty Filter** — Confidence-weighted position sizing

Only when all five models align do we pull the trigger.

---

## Features

### Real-Time Portfolio Tracking
- Live equity curve with high-water mark and drawdown visualization
- P&L updated every 5 seconds from Kalshi API
- No fake numbers. No demo mode fantasies. Real data or nothing.

### City-by-City Performance Matrix
- 10-city grid: NYC, CHI, LAX, MIA, AUS, DEN, PHL, BOS, SEA, SFO
- Win rate, net P&L, and trade count per city
- Scatter plot visualization: Win Rate vs. Profitability

### Automated Risk Management
Scaled for a **$992.10 bankroll** with proportional limits:

| Risk Parameter | Limit | Dollar Value |
|----------------|-------|--------------|
| Max per trade | 2% | $19.84 |
| Max city exposure | 3% | $29.76 |
| Max cluster exposure | 5% | $49.61 |
| Max daily loss | 5% | $49.61 |
| Max position size | 200 contracts | — |

Circuit breakers auto-pause trading on:
- Daily loss limit breach
- 5+ order rejections in 15 minutes
- API connectivity failures

### Binary Rogue Styling
- Dark theme with cyan/purple gradients
- Custom JetBrains Mono typography
- Tagline: *"Glitch The System. Burn The Map."*

---

## Installation

### Prerequisites
- Python 3.12+
- PostgreSQL 14+
- Kalshi API credentials (RSA key pair)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/milkbotai/Kalshi.git
cd Kalshi

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Kalshi API credentials and database URL

# Run database migrations
python -m src.shared.db.migrations.run

# Launch the dashboard
streamlit run src/dashboard/app.py --server.port 8501

# In a separate terminal, start the trading loop
python -m src.trader.trading_loop
```

### Kalshi API Setup

1. Generate an API key at [kalshi.com/account/api](https://kalshi.com/account/api)
2. Save your private key as `kalshi_private_key.pem` in the project root
3. Add to `.env`:
   ```
   KALSHI_API_KEY_ID=your-api-key-id
   KALSHI_PRIVATE_KEY_PATH=kalshi_private_key.pem
   ```

---

## Directory Structure

```
Kalshi/
├── src/
│   ├── dashboard/           # Streamlit UI
│   │   ├── app.py          # Main dashboard application
│   │   ├── components.py   # Reusable UI components
│   │   └── data.py         # Real-time data provider (Kalshi + NWS)
│   │
│   ├── trader/              # Trading engine
│   │   ├── trading_loop.py # Main execution loop
│   │   ├── strategies/     # Signal generation
│   │   │   └── daily_high_temp.py
│   │   ├── risk.py         # Risk calculator + circuit breaker
│   │   ├── gates.py        # Execution gates (spread, liquidity, edge)
│   │   └── oms.py          # Order management system
│   │
│   └── shared/              # Common utilities
│       ├── api/            # Kalshi & NWS API clients
│       ├── config/         # Settings, cities, logging
│       ├── db/             # Database models & repositories
│       └── constants.py    # System-wide constants
│
├── tests/                   # Unit & integration tests
├── data/                    # City configs & static data
├── .env.example             # Environment configuration template
└── requirements.txt         # Python dependencies
```

---

## Configuration

Key environment variables in `.env`:

```bash
# Trading Mode
TRADING_MODE=demo  # shadow | demo | live

# Risk Limits (scaled for $992.10 bankroll)
BANKROLL=992.10
MAX_TRADE_RISK_PCT=0.02
MAX_CITY_EXPOSURE_PCT=0.03
MAX_DAILY_LOSS_PCT=0.05

# Execution Gates
SPREAD_MAX_CENTS=4
LIQUIDITY_MIN=500
MIN_EDGE_AFTER_COSTS=0.03

# Strategy Optimization
# Only trade when edge >= 3% for higher win rate
```

---

## Trading Modes

| Mode | Description |
|------|-------------|
| `shadow` | Signals generated, no orders submitted, simulated fills |
| `demo` | Real orders to Kalshi demo API (paper trading) |
| `live` | **Real money.** Requires explicit confirmation. |

To enable live trading:
```python
from src.trader.trading_loop import TradingLoop, TradingMode

loop = TradingLoop(trading_mode=TradingMode.LIVE)
loop.confirm_live_mode()  # Explicit confirmation required
```

---

## Disclaimer: Black Flag Riders

**THIS IS NOT FINANCIAL ADVICE.**

MilkBot is an experimental, high-risk AI trading agent. By using this software, you acknowledge:

1. **You can lose money.** All of it. Quickly.
2. **Past performance means nothing.** Weather is chaotic. Markets are chaotic. MilkBot's edge is statistical, not guaranteed.
3. **This is not a get-rich-quick scheme.** It's a get-poor-quick scheme if you don't understand what you're doing.
4. **Binary Rogue is not a licensed financial advisor.** We build AI agents that read thermometers.
5. **Kalshi is a regulated exchange**, but prediction markets are still nascent territory with evolving rules.

If you're not comfortable with the possibility of losing your entire bankroll, **do not use this software**. Trade with money you can afford to lose. Set your risk limits. Respect the circuit breakers.

The Black Flag flies for those who understand: in the game of prediction markets, the house doesn't always win—but neither do the players who don't do their homework.

---

## Contributing

This is a private, proprietary system. The source code is not open for external contributions.

For authorized team members:
1. Create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass: `pytest tests/`
4. Submit a pull request with clear description

---

## License

Proprietary. All rights reserved.

Unauthorized copying, distribution, or use of this software is strictly prohibited.

---

<div align="center">

**Binary Rogue**

*Glitch The System. Burn The Map.*

MilkBot — First AI Agent Hire

</div>
