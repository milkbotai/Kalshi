# Observability (Logging, Metrics, Alerts)

## 1. Logging
- JSON structured logs.
- Correlation IDs per cycle.

### Required log events
- cycle_start/cycle_end
- weather_fetch_success/failure
- market_fetch_success/failure
- signal_generated (with p_yes, edge)
- risk_decision (caps applied)
- order_submitted / order_rejected
- fill_received
- circuit_breaker_triggered

## 2. Metrics
Expose (internal) metrics for:
- trades/day, signals/day
- avg spread paid
- fill rate, time-to-fill
- P&L, drawdown
- API latency and error rate

## 3. Alerts
- Trading paused
- Data stale
- Kalshi auth failures
- DB write failures
- Repeated rejects

---
