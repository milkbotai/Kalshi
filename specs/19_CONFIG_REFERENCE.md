# Configuration Reference

## 1. Environment separation
- dev
- demo
- live

Each environment has:
- separate Kalshi keys
- separate OpenRouter key
- separate DB (or schema prefix)

## 2. Config structure (YAML example)
```yaml
env: demo
bankroll: 5000
trade_delay_minutes: 60
cities:
  NYC:
    tz: America/New_York
    cluster: NE
    nws:
      office: OKX
      x: 33
      y: 37
    settlement_station: KNYC
risk:
  max_open_risk_pct: 0.10
  max_daily_loss_pct: 0.05
  max_trade_risk_pct: 0.02
execution:
  spread_max_cents: 3
  liq_min: 500
  repricer_interval_sec: 120
  max_chase_cents: 3
llm:
  enabled: true
  provider: openrouter
  model_fast: "<free_or_cheap_model_id>"
  model_deep: "<paid_model_id>"
  timeout_sec: 8
```

---
