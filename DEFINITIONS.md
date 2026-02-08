# Milkbot Kalshi Weather Trading Platform — System Definitions

**Version:** 1.0  
**Date:** 2026-01-23  
**Repo path (local):** `/Users/milkbot/Projects/Milkbot-Kalshi`  

## Purpose
Build an enterprise-grade, autonomous trading platform for **Kalshi weather/climate markets** and a **public-facing dashboard** at **milkbot.ai**.

Platform must be:
- **Deterministic** (same inputs → same outputs)
- **Auditable** (every trade reproducible from stored inputs)
- **Safe** (public UI never has trading keys)
- **Production-ready** on a single Ubuntu VPS (6 vCPU, 12GB RAM)

> Settlement reality: Kalshi weather markets resolve based on the **NWS daily climate report** and include a **DST-related day boundary nuance**. All trading logic must align to market rules. (See Kalshi Weather Markets docs.)

---

## Core Features (v1)
1. **Trading Engine (private)**
   - Market discovery for 10 cities
   - Weather ingestion (NWS primary) + caching
   - Strategy evaluation (probability-first)
   - Portfolio risk engine (caps + circuit breakers)
   - Order Management System (OMS) with idempotency + reconciliation

2. **Analytics Layer (internal)**
   - Postgres persistence of all events, snapshots, decisions
   - Rollups (city metrics, strategy metrics, equity curve)
   - Enforced **60-minute delayed** public trade feed

3. **Public Dashboard (milkbot.ai)**
   - Bloomberg-style dark UI
   - 10-city grid, 5s refresh
   - Exact trades displayed **>= 60 minutes after execution**

4. **LLM (OpenRouter) Advisory (optional)**
   - Explanation text + anomaly classification only
   - **Never** allowed to place/cancel orders or modify risk caps

---

## System Architecture
**Three services (single VPS):**

1. `trader` (private)
   - Holds Kalshi API credentials
   - Writes to Postgres `ops` schema

2. `analytics` (internal)
   - Reads `ops`, writes `analytics` rollups
   - Exposes internal endpoints (localhost only) OR dashboard reads views directly

3. `dashboard` (public)
   - Streamlit app
   - Reads *only* from `analytics` schema / internal API
   - **No secrets**

**Network boundary:**
- NGINX exposes only 80/443
- Postgres listens on localhost
- trader/analytics bind to localhost

---

## Target Cities (10)
- NYC, CHI, LAX, MIA, AUS, DEN, PHL, BOS, SEA, SFO

Each city requires:
- timezone
- NWS gridpoint mapping (office/x/y)
- settlement station identifier as referenced by market rules
- correlation cluster label (NE / SE / Midwest / Mountain / West)

---

## Trading Scope & Market Priority (profit-first)
**Priority order to implement (MVP → scale):**
1) **Daily High Temperature** markets (typically highest liquidity + simplest payoff)
2) **Daily Low Temperature** markets
3) **Monthly Rain** markets
4) **Monthly Snow** markets

Rationale: daily temp markets are the cleanest to model and trade; monthly precip adds year-round activity when daily temp markets are unavailable for a city.

---

## Business Rules
### Trading modes
- `SHADOW` (signals only, simulated fills)
- `DEMO` (demo orders)
- `LIVE` (production keys)

Default for development: `DEMO` or `SHADOW` only.

### Public disclosure
- Exact trades are shown with **60-minute delay**.
- Redact: order IDs, internal run IDs, raw request payloads.
- Round timestamps to minute for public view.

### Refresh and caching
- Dashboard refresh: every **5s**
- DB query cache: **5s**
- NWS weather cache per city: **5m**

### Execution gates (defaults)
- Spread ≤ **3¢**
- Liquidity ≥ configured minimum
- Minimum edge (after costs) ≥ configured minimum

### Risk policy (design-time defaults for $5,000 demo bankroll; live values in Settings)
- Max open risk: **$500** (10%)
- Max daily loss: **$250** (5%) → pause 24h
- Max per trade risk: **$100** (2%)
- Max city exposure: **$150** (3%)
- Max cluster exposure: **$250** (5%)

### Circuit breakers
Pause trading when:
- daily loss limit hit
- repeated order rejects (N within M minutes)
- weather data stale beyond threshold
- DB write failures

---

## Data Models (authoritative)
### Domain models
- **CityConfig**: city code, tz, cluster, NWS mapping, settlement station
- **WeatherSnapshot**: captured_at, forecast/obs payloads, data freshness flags
- **MarketSnapshot**: captured_at, bid/ask, volume/open_interest, close_time, rules_url
- **Signal**: strategy outputs (p_yes, uncertainty, edge), decision, reason codes
- **Order**: intent_key, side, qty, limit_price, status, kalshi_order_id
- **Fill**: order_id, filled_at, qty, price
- **Position**: market_id, side, qty, avg entry/exit, pnl, status
- **RiskEvent**: event_type, severity, payload
- **HealthStatus**: component status, last_ok, message

### Database layout (Postgres)
- Schema `ops`: all raw snapshots, signals, orders, fills, positions, risk/system events
- Schema `analytics`: rollups and *public-safe* views

**Required analytics view:** `analytics.v_public_trades`
- Only includes trades where `trade_time <= now() - interval '60 minutes'`

---

## External Integrations
### Kalshi Trading API
- Demo + Live environments
- Functions needed: list markets/series, get orderbook, create/cancel orders, get positions, get fills

### NWS (weather.gov)
- Used for forecast/obs inputs and alignment with settlement source
- Must respect caching and backoff

### OpenRouter LLM (optional)
- OpenAI-compatible API
- Used for explanation/anomaly labels only

---

## Error Handling
### Network/API failures
- Retry with exponential backoff
- Use cached weather snapshots within TTL
- If stale beyond threshold → mark degraded and pause trading

### Data validation
- Reject trades if required fields missing
- Reject trades if market snapshot too old

### DB failures
- If trader cannot persist → pause trading immediately
- Dashboard continues with cached metrics if available

---

## Testing Strategy
### Unit tests
- Strategy math + edge computations
- Risk caps + circuit breaker logic
- OMS state transitions + idempotency key generation
- Analytics queries + delay enforcement

### Integration tests
- End-to-end cycle with mocked Kalshi + mocked NWS
- Postgres persistence and rollup generation
- Restart reconciliation test (no duplicated orders)

### Performance tests
- Dashboard critical queries under 100ms (where feasible)
- Rollups complete within defined time budget

---

## Performance Requirements
- Public dashboard initial load < 2s
- Refresh cycle < 500ms server-side work
- All services auto-restart (systemd)

---
