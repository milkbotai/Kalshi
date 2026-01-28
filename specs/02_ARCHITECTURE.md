# System Architecture

## 1. High-level design
Milkbot is a **three-service** architecture on a single VPS:

- **Trader (private):** trading decisions and execution.
- **Analytics API (internal):** sanitized read model for dashboard.
- **Dashboard (public):** Streamlit UI at milkbot.ai.

### 1.1 Data flow
```text
(NWS + other forecasts)    (Kalshi API)
        |                    |
        v                    v
  Ingestion & Cache      Market Discovery
        |                    |
        +--------+-----------+
                 v
        Feature Computation
                 |
                 v
     Strategy Ensemble -> Probabilities
                 |
                 v
          Risk Engine (portfolio)
                 |
                 v
       Order Management System (OMS)
                 |
                 v
      Orders/Fills/Positions persisted
                 |
                 v
     Analytics rollups + delayed views
                 |
                 v
        Public Dashboard (milkbot.ai)
```

## 2. Key principles
### 2.1 Isolation boundary
- Dashboard must **never** connect to Kalshi with trading credentials.
- Dashboard reads only from analytics schema or internal API.

### 2.2 Auditability
For every trade, store:
- market snapshot (prices, liquidity, spread, close time, rules URL)
- weather snapshot (forecasts, observations, source timestamps)
- strategy outputs (p_yes, uncertainty, features)
- risk decision (caps applied, reason codes)
- OMS decision (limit price, cancel/replace policy)

### 2.3 Determinism
- Strategy outputs are deterministic given inputs (no stochastic LLM decisions).
- LLM output is advisory metadata only.

## 3. Components
### 3.1 Ingestion layer
- NWS forecast and observation pulls per city with TTL caching.
- Optional secondary forecast provider for cross-validation.

### 3.2 Market discovery
- Identify relevant active markets per city and timeframe.
- Normalize Kalshi market/contract identifiers into internal models.

### 3.3 Strategy engine
- Multiple strategies produce probability estimates.
- Ensemble layer merges to a final probability.

### 3.4 Risk engine
- Per-trade sizing constrained by portfolio caps.
- Correlation clustering across cities (rolling window).
- Drawdown circuit breakers.

### 3.5 OMS
- State machine for orders.
- Idempotency keys for “intent”.
- Reconciliation on restart.

### 3.6 Analytics API
- Computes city metrics, strategy metrics, equity curve.
- Enforces 60-minute trade delay in queries.

### 3.7 Public dashboard
- 10-city grid, dark mode theme.
- 5-second refresh; caching to protect DB.

---
