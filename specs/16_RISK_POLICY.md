# Risk Policy (Enterprise Defaults)

> **Note:** This is the original design spec. Live values are now managed via `src/shared/config/settings.py` and `.env`. Current live bankroll: $992.10.

## 1. Bankroll
- Demo bankroll: **$5,000** *(design-time default; superseded by Settings)*

## 2. Risk limits (defaults; tune during demo)
### 2.1 Portfolio caps
- **Max open risk**: 10% bankroll = $500
- **Max daily loss**: 5% bankroll = $250 → pause 24h
- **Max weekly loss**: 12% bankroll = $600 → reduce size 50%
- **Max monthly loss**: 20% bankroll = $1,000 → safe mode only

### 2.2 Per-trade caps
- **Max per trade risk**: 2% bankroll = $100
- **Max contracts per trade**: min(95, floor(max_trade_risk/$1))

### 2.3 Per-city caps
- **Max city exposure**: 3% bankroll = $150

### 2.4 Correlation cluster caps
Clusters: NE, SE, Midwest, Mountain, West
- **Max cluster exposure**: 5% bankroll = $250

## 3. Execution gates
- Spread <= 3¢ (default)
- Liquidity >= configured minimum
- Avoid trading within last X minutes if spreads widen

## 4. Circuit breakers
Trigger pause when:
- daily loss limit hit
- repeated order rejects (>=N per M minutes)
- data stale beyond threshold
- DB write failures

## 5. Risk reporting
Every cycle produce:
- exposure by city and cluster
- open risk and worst-case loss
- realized P&L, drawdown

---
