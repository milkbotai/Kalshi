# Data Model (PostgreSQL)

## 1. Database
- PostgreSQL (single instance)
- Two schemas:
  - `ops` — private operational data
  - `analytics` — sanitized views/rollups for public UI

## 2. ops schema (minimum)
### 2.1 ops.weather_snapshots
- id (pk)
- city
- captured_at (ts)
- nws_forecast (jsonb)
- nws_observation (jsonb)
- secondary_forecast (jsonb, nullable)
- normals (jsonb)
- data_quality_flags (jsonb)

### 2.2 ops.market_snapshots
- id (pk)
- market_id
- captured_at
- yes_bid/ask
- no_bid/ask
- volume/open_interest
- close_time
- rules_url

### 2.3 ops.signals
- id (pk)
- created_at
- city
- market_id
- strategy
- p_yes
- uncertainty
- edge_estimate
- decision (TRADE/HOLD)
- reason_codes (jsonb)

### 2.4 ops.orders
- id (pk)
- intent_key (unique)
- created_at
- market_id
- side (YES/NO)
- limit_price
- qty
- status
- kalshi_order_id (nullable)

### 2.5 ops.fills
- id (pk)
- order_id (fk)
- filled_at
- qty
- price

### 2.6 ops.positions
- id (pk)
- opened_at
- closed_at (nullable)
- city
- market_id
- side
- qty
- avg_entry
- avg_exit (nullable)
- realized_pnl (nullable)
- status (OPEN/CLOSED)

### 2.7 ops.risk_events
- id (pk)
- ts
- event_type (DAILY_LIMIT_HIT, CLUSTER_CAP, etc.)
- severity
- payload (jsonb)

## 3. analytics schema
### 3.1 analytics.v_public_trades (view)
**Must enforce 60-minute delay.**
- trade_time
- city
- market_id
- side
- qty
- price
- strategy
- pnl (when known)

Filter rule: `trade_time <= now() - interval '60 minutes'`

### 3.2 analytics.city_metrics
- city
- total_pnl
- daily_pnl
- win_rate
- trades_today
- active_positions
- updated_at

### 3.3 analytics.strategy_metrics
- strategy
- total_pnl
- win_rate
- trade_count

### 3.4 analytics.health_status
- component (trader, db, nws, kalshi)
- status (OK/DEGRADED/DOWN)
- last_ok
- message

---
