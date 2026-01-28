# Strategy Specification

## 0. Design goals
- **Deterministic**: same inputs → same outputs.
- **Probability-first**: every strategy outputs a calibrated probability estimate (`p_yes`) and uncertainty.
- **Cost-aware**: only trade if **expected value after costs** exceeds a configurable minimum.
- **Market-aware**: prefer higher liquidity and tighter spreads.

## 1. Inputs (per city/market)
- Weather:
  - NWS forecast (primary)
  - NWS observations (for trend/nowcast)
  - Climate normals (baseline mean/std)
  - Precip probability (for temp impact)
- Market:
  - yes/no bid/ask
  - volume / open interest
  - close time
  - rules URL (for settlement)

## 2. Outputs (standard contract)
```json
{
  "strategy": "mean_reversion",
  "p_yes": 0.42,
  "uncertainty": 0.12,
  "edge": 0.031,
  "action": "BUY",
  "side": "NO",
  "max_price": 0.64,
  "reasons": ["z_score_extreme", "spread_ok", "sources_ok"],
  "features": {"z": 2.3, "spread": 0.02, "liq": 12000}
}
```

## 3. Strategy 1 — Mean Reversion (Primary)
### Concept
Markets can overreact to forecast extremes. Use z-score vs normals to estimate probability of threshold.

### Features
- `z = (forecast_temp - baseline_mean) / baseline_std`
- regime-adjusted mean (optional)

### Probability mapping
Start simple and calibrate:
- Use a logistic mapping from z-score to probability of exceeding a threshold.
- Calibrate parameters nightly using last N days of outcomes.

### Entry
- `abs(z) >= Z_THRESHOLD`
- spread <= SPREAD_MAX
- liquidity >= LIQ_MIN
- time_to_close within window

### Exit
- before close (avoid late liquidity traps)
- or if edge collapses

## 4. Strategy 2 — Trend / Nowcast Adjustment
### Concept
Short-term observation trend can reveal forecast lag.

### Features
- `velocity = (temp_now - temp_6h_ago)/6`
- deviation of obs vs forecast at same timestamp

### Rules
- Only apply when data freshness is good.
- Dampened in high volatility cities.

## 5. Strategy 3 — Precipitation Correlation
### Concept
Precip often shifts temperature distribution.

### Features
- precip probability (NWS hourly)
- wind speed (optional)

### Rules
- Adjust baseline mean by a city/season calibrated delta when precip probability exceeds threshold.

## 6. Strategy 4 — Extreme/Record Likelihood (Revised)
The naive “1/(years since record)” approach is not used.

### Alternative
- Use historical distribution of highs for the date window (from normals or station history).
- Estimate tail probability using an extreme-value / empirical percentile method.

## 7. Ensemble layer
Combine strategies with weighted average:
- weights are learned from demo period and rolled forward
- if a strategy is invalid (`valid=false`) it contributes 0 weight

## 8. Minimum edge rule
Compute market implied probability from mid price.
- `p_mkt_yes = mid_yes`
- `edge_yes = p_model_yes - p_mkt_yes`

Only trade if:
- `edge_after_costs >= MIN_EDGE`

## 9. LLM usage
LLM can annotate:
- regime labels
- explanation text
LLM cannot alter `p_yes` or execute trades.

---
