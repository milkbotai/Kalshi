# Risk Policy (Enterprise Defaults)

> **Note:** This is the original design spec. Live values are managed via `src/shared/config/settings.py` and `.env`. Current live bankroll: **$992.10**. All dollar amounts below scale with the configured bankroll.

## 1. Bankroll
- Configured via `BANKROLL` in `.env` (current: $992.10)

## 2. Risk limits (percentages; dollar amounts scale with bankroll)
### 2.1 Portfolio caps
- **Max open risk**: 10% of bankroll
- **Max daily loss**: 5% of bankroll → pause 24h
- **Max weekly loss**: 12% of bankroll → reduce size 50%
- **Max monthly loss**: 20% of bankroll → safe mode only

### 2.2 Per-trade caps
- **Max per trade risk**: 2% of bankroll
- **Max contracts per trade**: min(95, floor(max_trade_risk/$1))

### 2.3 Per-city caps
- **Max city exposure**: 3% of bankroll

### 2.4 Correlation cluster caps
Clusters: NE, SE, Midwest, Mountain, West
- **Max cluster exposure**: 5% of bankroll

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
