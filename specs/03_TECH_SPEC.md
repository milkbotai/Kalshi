# Technical Specification

## 1. Repository layout
```text
milkbot/
  src/
    trader/
      ingestion/
      markets/
      features/
      strategies/
      ensemble/
      risk/
      oms/
      settlement/
      jobs/
    analytics/
      api/
      queries/
      rollups/
    dashboard/
      app.py
      components/
      styles.css
    shared/
      models/
      config/
      logging/
  tests/
    unit/
    integration/
    fixtures/
  infra/
    nginx/
    systemd/
    migrations/
  docs/
```

## 2. Language and standards
- Python 3.11+
- Type hints everywhere; mypy strict.
- Black + isort; ruff optional.
- Structured logging (JSON).

## 3. Scheduling
Two loops:
- **Fast loop (every 60s):** market discovery + pricing snapshots + signal evaluation.
- **Slow loop (every 5–15m):** NWS refresh, regime update, rollups.

## 4. Strategy output contract
Each strategy returns:
```json
{
  "strategy": "mean_reversion",
  "p_yes": 0.42,
  "uncertainty": 0.12,
  "features": {"z_score": 2.3, "spread": 0.02},
  "valid": true,
  "reasons": ["sources_agree", "edge_after_costs"]
}
```

## 5. Ensemble contract
```json
{
  "p_yes": 0.45,
  "p_no": 0.55,
  "confidence": 0.73,
  "explain": "weighted ensemble",
  "inputs": ["<strategy outputs>"]
}
```

## 6. Risk engine requirements
### 6.1 Caps
- Max open risk (absolute $) and percentage of bankroll.
- Max exposure per city.
- Max exposure per correlation cluster.
- Max number of concurrent positions.
- Daily loss limit triggers trading pause.

### 6.2 Sizing
- Suggested: fractional Kelly constrained by caps.
- Hard floor: do not trade below minimum edge after costs.

## 7. OMS requirements
### 7.1 Order state machine
States: NEW → SUBMITTED → RESTING → PARTIAL → FILLED → CANCELED/REJECTED → CLOSED

### 7.2 Idempotency
An “intent” must have an idempotency key:
- city + market_id + side + strategy + event_date
No intent can place two orders unless intent is explicitly superseded.

### 7.3 Cancel/replace policy
- Do not chase price beyond N cents.
- Cancel if spread widens or liquidity drops below threshold.

## 8. Settlement rules module
- Store settlement source URL per market.
- Maintain correct day boundary handling per market rules.

---
