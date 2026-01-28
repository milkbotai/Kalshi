# Internal API Contracts (Analytics Service)

> The public dashboard should call only these endpoints (or query read-only views directly).

## 1. Auth
- Internal only (localhost) OR protected by firewall/VPN.
- Public dashboard service can access internal API via localhost.

## 2. Endpoints
### 2.1 GET /v1/metrics/hero
Returns top-level KPIs.
```json
{
  "total_pnl": 1234.56,
  "win_rate": 74.2,
  "trades_today": 18,
  "active_positions": 6,
  "mode": "DEMO",
  "as_of": "2026-01-23T19:25:00Z"
}
```

### 2.2 GET /v1/metrics/cities
Returns per-city metrics for 10-city grid.
```json
{
  "as_of": "...",
  "cities": [
    {"city":"NYC","current_temp":41.2,"active_positions":1,"city_total_pnl":210.5,"city_win_rate":68.0,"status":"ACTIVE","data_age_seconds":120},
    {"city":"LAX","current_temp":58.1,"active_positions":0,"city_total_pnl":44.0,"city_win_rate":75.0,"status":"IDLE","data_age_seconds":240}
  ]
}
```

### 2.3 GET /v1/trades/recent?limit=200
Returns **delayed trades only**.
```json
{
  "delay_minutes": 60,
  "trades": [
    {"trade_time":"...","city":"NYC","market_id":"...","side":"NO","qty":25,"price":0.62,"strategy":"mean_reversion","status":"FILLED"}
  ]
}
```

### 2.4 GET /v1/performance/equity?days=30
Equity curve for Plotly chart.

### 2.5 GET /v1/health
System health summary.

---
