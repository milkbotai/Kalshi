# Product Requirements Document (PRD)

**Product:** Milkbot Weather Trading Platform for Kalshi  
**Version:** 1.0  
**Date:** 2026-01-23

## 1. Executive summary
Milkbot is an autonomous trading platform focused on **Kalshi weather/climate markets** across **10 US cities**.

It includes:
- a private trading engine (demo → live),
- an internal analytics layer,
- a public-facing dashboard at **milkbot.ai**.

**Primary objective:** build a production-grade system that can trade at high cadence while maintaining strict risk controls and full audit trails.

## 2. Goals
### 2.1 Functional goals
1) Trade across 10 target cities year-round (daily temps + monthly rain/snow markets to maintain activity).
2) Execute trades with deterministic rules, strict validation, and circuit breakers.
3) Provide a public dashboard displaying performance and **exact trades delayed by 60 minutes**.
4) Maintain complete observability: decision logs, market snapshots, weather snapshots, orders/fills, and risk events.

### 2.2 Non-functional goals (enterprise-grade)
- High availability: automatic restart; graceful degradation when APIs are stale.
- Security: keys never exposed to public UI; secrets managed safely.
- Performance: dashboard refresh <2s; DB queries <100ms where feasible.
- Auditability: every trade must be reproducible from stored inputs (market snapshot + weather snapshot + config version).

## 3. Success metrics
- **Stability:** 0 duplicated orders from restarts; 0 unhandled exceptions in steady state.
- **Risk adherence:** daily/weekly/monthly drawdown limits trigger correctly; exposure caps respected.
- **Execution quality:** track spread, slippage, fill rate, time-to-fill.
- **Forecast edge tracking:** realized edge after costs is measured; alerts fire if edge decays.

## 4. Constraints
- Deployment target: single VPS (Ubuntu) with 6 cores / 12GB RAM / 200GB disk.
- Public domain: milkbot.ai behind Cloudflare.
- Trading starts in demo for 10 days (paper/dry-run policy) before any live exposure.
- LLM use via OpenRouter is **advisory** only (no direct trade placement authority).

## 5. Scope
### In scope (v1)
- 10-city trading across applicable Kalshi climate/weather markets.
- Data ingestion: NWS (primary), climate normals (baseline), optional secondary forecast provider.
- Strategy engine: interpretable statistical strategies + ensemble probability layer.
- Risk engine: portfolio + city + correlation cluster controls.
- OMS (order management): idempotency, reconciliation, state machine.
- Public dashboard: Set-2-style UI, exact trades with 60-minute delay.

### Out of scope (v1)
- High-frequency (sub-second) trading.
- Fully autonomous self-modifying strategy logic.
- Mobile app.

## 6. Personas & user stories
### 6.1 Operator (internal)
- View live positions, exposures, and risk status.
- Pause trading instantly (kill switch).
- Receive alerts on incidents and risk events.

### 6.2 Public viewer
- See updated performance metrics and charts.
- See exact trades with a 60-minute delay.

### 6.3 Engineer
- Add a new city via config.
- Add a new strategy module with tests.
- Run simulation/backtest and compare to live.

## 7. Acceptance criteria (MVP)
- System runs continuously for 72 hours with no crashes.
- End-to-end pipeline works: ingest → signal → risk → order (demo) → fill tracking → P&L.
- Public dashboard loads at milkbot.ai, shows 10 cities, updates every 5s.
- Trade delay enforcement: no trade appears publicly until >=60 minutes after trade timestamp.

---
