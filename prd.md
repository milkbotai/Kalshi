# Milkbot Kalshi – PRD
Order: foundation → models → DB → trader → analytics → dashboard → deployment.

---

## Phase 1: Foundation (Stories 1.1–1.5)

### Story 1.1 – Constants & Test Fixtures
Create constants for delays/refresh and provide test fixtures.

**Acceptance Criteria**
- Constants exist with exact values from DEFINITIONS.md (PUBLIC_TRADE_DELAY_MIN=60, DASH_REFRESH_SEC=5, WEATHER_CACHE_MIN=5).
- Three fixtures (sample_market_snapshot, sample_weather_snapshot, sample_order_fill) import without error.
- `pytest -v` runs and all tests pass.
- mypy passes on constants module.
- No external dependencies (DB, API calls).

### Story 1.2 – Logging Infrastructure
Set up structured logging with no secrets exposure.

**Acceptance Criteria**
- Logger configured with JSON formatter for production, human-readable for dev.
- Log levels configurable via environment variable.
- Test verifies secrets (containing "key", "token", "password") are redacted from log output.
- No print() statements allowed in codebase (enforced by test).
- Logger available as `milkbot.logger`.

### Story 1.3 – Environment Configuration
Create config loader for environment variables and modes.

**Acceptance Criteria**
- Config class loads TRADING_MODE (SHADOW/DEMO/LIVE), DB connection string, API keys.
- Validates required fields on startup.
- Defaults to SHADOW mode if not specified.
- Test verifies missing required config raises clear error.
- Secrets never logged or exposed in repr().

### Story 1.4 – City Configuration Data
Define 10-city configuration with timezone, NWS mapping, cluster.

**Acceptance Criteria**
- CityConfig Pydantic model with fields: code, name, timezone, cluster, nws_office, nws_grid_x, nws_grid_y, settlement_station.
- JSON file with all 10 cities (NYC, CHI, LAX, MIA, AUS, DEN, PHL, BOS, SEA, SFO).
- Loader function returns dict[str, CityConfig].
- Test validates all cities have valid timezones and cluster assignments.
- Test verifies NWS grid coordinates are integers.

### Story 1.5 – Domain Models (Pydantic)
Define core Pydantic models for weather, markets, signals, orders, fills, positions.

**Acceptance Criteria**
- Models defined: WeatherSnapshot, MarketSnapshot, Signal, Order, Fill, Position, RiskEvent, HealthStatus.
- Each model validates example payload from fixture.
- Unit tests cover happy path and validation errors (missing fields, wrong types).
- All models have frozen=True or appropriate mutability settings.
- Datetime fields use timezone-aware types.

---

## Phase 2: Database Layer (Stories 2.1–2.8)

### Story 2.1 – Database Connection Manager
Create Postgres connection pool with health checks.

**Acceptance Criteria**
- Connection manager supports context manager protocol.
- Health check function returns True if DB reachable.
- Configurable pool size and timeout.
- Test with in-memory SQLite or test Postgres instance.
- Graceful shutdown releases all connections.

### Story 2.2 – Schema Migration Framework
Set up Alembic or raw SQL migration system.

**Acceptance Criteria**
- Migration tool initialized with `ops` and `analytics` schemas.
- Migration 001 creates both schemas.
- `migrate up` and `migrate down` commands work.
- Test verifies schemas exist after migration.
- Migration history tracked in DB.

### Story 2.3 – Ops Schema Tables (Weather & Markets)
Create tables for weather_snapshots and market_snapshots.

**Acceptance Criteria**
- Tables created with proper indexes (city_code, captured_at).
- JSONB columns for raw payloads.
- Insert test data and verify retrieval.
- Foreign key constraints where applicable.
- Test verifies schema matches Pydantic models.

### Story 2.4 – Ops Schema Tables (Trading)
Create tables for signals, orders, fills, positions.

**Acceptance Criteria**
- Tables include intent_key (unique), timestamps, status enums.
- orders table has kalshi_order_id (nullable, unique when set).
- fills table references orders.
- positions table tracks open/closed status.
- Test inserts full trade lifecycle (signal → order → fill → position).

### Story 2.5 – Ops Schema Tables (Risk & Health)
Create tables for risk_events and health_status.

**Acceptance Criteria**
- risk_events table with severity enum, event_type, payload JSONB.
- health_status table with component name, last_ok timestamp, message.
- Indexes on timestamp and severity/component.
- Test inserts sample events and queries recent entries.
- Retention policy documented (not enforced yet).

### Story 2.6 – Repository Pattern (Weather & Markets)
Implement repository classes for weather and market data.

**Acceptance Criteria**
- WeatherRepository with save_snapshot() and get_latest(city_code).
- MarketRepository with save_snapshot() and get_active_markets(city_code).
- Methods return Pydantic models, not raw dicts.
- Unit tests with mocked DB verify SQL correctness.
- Integration test with test DB verifies round-trip.

### Story 2.7 – Repository Pattern (Trading)
Implement repository classes for signals, orders, fills, positions.

**Acceptance Criteria**
- SignalRepository, OrderRepository, FillRepository, PositionRepository.
- OrderRepository.create() generates intent_key if not provided.
- get_by_intent_key() supports idempotency checks.
- Test verifies duplicate intent_key raises or returns existing.
- All timestamps stored as UTC.

### Story 2.8 – Analytics Schema & Public Trade View
Create analytics schema with 60-minute delayed trade view.

**Acceptance Criteria**
- Migration creates `analytics` schema.
- View `analytics.v_public_trades` joins fills + orders + markets.
- WHERE clause filters `fill_time <= now() - interval '60 minutes'`.
- Redacts: order_id, intent_key, raw payloads.
- Test query returns empty set for recent trades, includes older trades.

---

## Phase 3: External Integrations (Stories 3.1–3.6)

### Story 3.1 – Kalshi API Client (Auth & Markets)
Implement Kalshi API authentication and market discovery.

**Acceptance Criteria**
- Client supports demo and live base URLs.
- authenticate() returns token, handles errors.
- list_markets(series_ticker) returns list of MarketSnapshot.
- Retry logic with exponential backoff (3 attempts).
- Unit tests mock HTTP responses.

### Story 3.2 – Kalshi API Client (Orderbook)
Implement orderbook fetching.

**Acceptance Criteria**
- get_orderbook(market_ticker) returns bid/ask/volume.
- Parses Kalshi response into MarketSnapshot.
- Handles missing orderbook (market closed/halted).
- Test verifies spread calculation.
- Rate limiting respected (documented, not enforced yet).

### Story 3.3 – Kalshi API Client (Orders)
Implement order placement and cancellation.

**Acceptance Criteria**
- create_order(market_ticker, side, qty, limit_price, client_order_id) returns order_id.
- cancel_order(order_id) returns success boolean.
- Handles API errors (insufficient balance, invalid market, etc.).
- Test with mocked responses verifies request payload.
- client_order_id used for idempotency.

### Story 3.4 – Kalshi API Client (Positions & Fills)
Implement position and fill retrieval.

**Acceptance Criteria**
- get_positions() returns list of Position models.
- get_fills(since_timestamp) returns list of Fill models.
- Pagination handled if needed.
- Test verifies timestamp filtering.
- Handles empty results gracefully.

### Story 3.5 – NWS API Client (Forecast & Observations)
Implement NWS weather data fetching.

**Acceptance Criteria**
- get_forecast(office, grid_x, grid_y) returns forecast periods.
- get_observation(station_id) returns latest temp/conditions.
- Parses NWS JSON into WeatherSnapshot model.
- Retry with backoff on 5xx errors.
- Test mocks NWS responses.

### Story 3.6 – Weather Cache Layer
Implement 5-minute cache for NWS data per city.

**Acceptance Criteria**
- Cache keyed by city_code, TTL=5 minutes.
- get_weather(city_code) returns cached if fresh, else fetches.
- Staleness flag set if data older than threshold (15 min).
- Test verifies cache hit/miss behavior.
- Thread-safe if needed.

---

## Phase 4: Trading Engine (Stories 4.1–4.10)

### Story 4.1 – Strategy Interface
Define abstract strategy class and probability calculator.

**Acceptance Criteria**
- Strategy base class with evaluate(weather, market) → Signal.
- Signal includes p_yes, uncertainty, edge, decision (BUY/SELL/HOLD).
- Probability calculator for temperature thresholds (normal distribution).
- Test verifies edge = p_yes - market_price (simplified).
- Reason codes enumerated.

### Story 4.2 – Daily High Temperature Strategy
Implement strategy for daily high temp markets.

**Acceptance Criteria**
- Uses forecast high temp and historical variance.
- Calculates p_yes for "high >= threshold" markets.
- Returns HOLD if uncertainty > configured max.
- Test with known inputs verifies probability output.
- Edge calculation includes estimated transaction costs.

### Story 4.3 – Execution Gate Checks
Implement pre-trade validation (spread, liquidity, edge).

**Acceptance Criteria**
- check_spread(market) returns True if spread <= 3¢.
- check_liquidity(market, qty) returns True if sufficient.
- check_edge(signal) returns True if edge >= min_edge config.
- Test verifies each gate independently.
- Logs reason when gate fails.

### Story 4.4 – Risk Calculator (Position Limits)
Implement position and exposure limit checks.

**Acceptance Criteria**
- calculate_open_risk(positions) returns total at-risk capital.
- check_city_exposure(city_code, new_trade) enforces city limit.
- check_cluster_exposure(cluster, new_trade) enforces cluster limit.
- check_trade_size(trade) enforces per-trade max.
- Test verifies limits block oversized trades.

### Story 4.5 – Risk Calculator (Circuit Breakers)
Implement daily loss and error-based circuit breakers.

**Acceptance Criteria**
- track_daily_pnl() calculates realized + unrealized PnL.
- check_daily_loss_limit() pauses trading if loss >= $250.
- track_order_rejects() counts failures in sliding window.
- Pause triggered if N rejects in M minutes.
- Test verifies pause state persists until reset.

### Story 4.6 – Order Management System (OMS) Core
Implement OMS with idempotency and state tracking.

**Acceptance Criteria**
- generate_intent_key(signal) creates deterministic key.
- submit_order(signal) checks for existing intent_key before creating.
- State machine: PENDING → SUBMITTED → FILLED/CANCELLED/REJECTED.
- Test verifies duplicate submission returns existing order.
- All state transitions logged.

### Story 4.7 – OMS Reconciliation
Implement startup reconciliation of orders and fills.

**Acceptance Criteria**
- reconcile() fetches Kalshi fills since last run.
- Matches fills to local orders by client_order_id.
- Updates order status and creates fill records.
- Detects orphaned fills (no local order) and logs warning.
- Test with mocked Kalshi data verifies matching logic.

### Story 4.8 – Trading Loop (Single City)
Implement main trading loop for one city.

**Acceptance Criteria**
- Loop: fetch weather → fetch markets → evaluate strategy → check gates → submit orders.
- Runs once per invocation (no infinite loop yet).
- Persists all snapshots and signals to DB.
- Test with mocked APIs verifies full cycle.
- Errors logged, loop continues (no crash).

### Story 4.9 – Multi-City Orchestration
Extend trading loop to handle all 10 cities.

**Acceptance Criteria**
- Iterates over all cities in config.
- Parallelizes API calls where safe (weather fetching).
- Aggregates risk across all cities before each trade.
- Test verifies cluster exposure enforced across cities.
- Logs summary stats per cycle.

### Story 4.10 – Trading Mode Enforcement
Implement SHADOW/DEMO/LIVE mode switching.

**Acceptance Criteria**
- SHADOW: signals generated, no orders submitted, simulated fills.
- DEMO: uses demo API keys and endpoints.
- LIVE: uses production keys (requires explicit confirmation).
- Mode logged at startup and in every order record.
- Test verifies SHADOW mode never calls Kalshi order API.

---

## Phase 5: Analytics & Rollups (Stories 5.1–5.6)

### Story 5.1 – City Metrics Rollup
Create rollup table for per-city performance.

**Acceptance Criteria**
- Table: analytics.city_metrics (city_code, date, trades, pnl, win_rate).
- Scheduled job (or manual function) aggregates from ops.fills.
- Test verifies metrics match raw data.
- Incremental updates (only new data processed).
- Indexed by city_code and date.

### Story 5.2 – Strategy Metrics Rollup
Create rollup table for per-strategy performance.

**Acceptance Criteria**
- Table: analytics.strategy_metrics (strategy_name, date, signals, trades, edge_realized).
- Aggregates from ops.signals and ops.fills.
- Test verifies edge_realized = avg(fill_price - signal.p_yes).
- Handles multiple strategies (future-proof).
- Daily granularity.

### Story 5.3 – Equity Curve Rollup
Create rollup table for portfolio equity over time.

**Acceptance Criteria**
- Table: analytics.equity_curve (timestamp, total_equity, realized_pnl, unrealized_pnl).
- Snapshots taken at end of each trading cycle.
- Test verifies equity = starting_capital + realized_pnl + unrealized_pnl.
- Handles missing data (gaps in trading).
- Queryable for charting.

### Story 5.4 – Public Trade Feed (60-Minute Delay)
Implement analytics view for public trade disclosure.

**Acceptance Criteria**
- View `analytics.v_public_trades` enforces `fill_time <= now() - interval '60 minutes'`.
- Columns: city, market_type, side, qty, price, fill_time (rounded to minute).
- Excludes: order_id, intent_key, client_order_id, raw payloads.
- Test verifies trades within 60 min are excluded.
- Test verifies older trades are included.

### Story 5.5 – Health Metrics Aggregation
Create view for system health dashboard.

**Acceptance Criteria**
- View `analytics.v_health_summary` shows latest status per component.
- Components: trader, analytics, dashboard, kalshi_api, nws_api, database.
- Includes last_ok timestamp and current message.
- Test verifies degraded components flagged.
- Queryable in <50ms.

### Story 5.6 – Analytics API (Internal)
Create internal HTTP API for dashboard queries.

**Acceptance Criteria**
- FastAPI or Flask app with endpoints: /metrics/city, /metrics/strategy, /equity, /trades/public, /health.
- Binds to localhost only.
- Returns JSON with proper CORS headers (for Streamlit).
- Test verifies 60-minute delay enforced in /trades/public.
- Rate limiting documented (not enforced yet).

---

## Phase 6: Public Dashboard (Stories 6.1–6.8)

### Story 6.1 – Streamlit App Scaffold
Create basic Streamlit app structure.

**Acceptance Criteria**
- App runs with `streamlit run dashboard.py`.
- Dark theme configured (Bloomberg-style).
- Page title and favicon set.
- Auto-refresh every 5 seconds.
- No secrets or API keys in code.

### Story 6.2 – 10-City Grid Layout
Implement grid layout for 10 cities.

**Acceptance Criteria**
- 2 rows × 5 columns grid (or responsive layout).
- Each cell shows city name, current temp, market status.
- Placeholder data initially.
- Test verifies all 10 cities rendered.
- Consistent typography and spacing.

### Story 6.3 – Live Market Data Display
Connect grid to analytics API for real-time market data.

**Acceptance Criteria**
- Fetches latest market snapshots from analytics API.
- Displays bid/ask, spread, volume per city.
- Updates every 5 seconds.
- Handles missing data gracefully (shows "N/A").
- Test verifies API call on each refresh.

### Story 6.4 – Public Trade Feed Display
Display delayed trades in scrollable table.

**Acceptance Criteria**
- Queries `analytics.v_public_trades` via API.
- Table columns: time (rounded to minute), city, side, qty, price.
- Sorted by time descending (most recent first).
- Test verifies no trades within 60 minutes shown.
- Pagination or limit to last 100 trades.

### Story 6.5 – Equity Curve Chart
Display portfolio equity over time.

**Acceptance Criteria**
- Line chart using Plotly or Altair.
- X-axis: time, Y-axis: total equity.
- Shows last 30 days by default.
- Hover tooltip shows realized/unrealized PnL.
- Test verifies chart renders with sample data.

### Story 6.6 – City Performance Heatmap
Display win rate and PnL per city.

**Acceptance Criteria**
- Heatmap or table with color coding (green=profit, red=loss).
- Columns: city, trades, win_rate, total_pnl.
- Sortable by any column.
- Test verifies data matches analytics rollup.
- Updates on refresh.

### Story 6.7 – System Health Indicator
Display health status of all components.

**Acceptance Criteria**
- Status badges (green/yellow/red) for each component.
- Shows last_ok timestamp and message.
- Alerts if any component degraded.
- Test verifies degraded state triggers visual alert.
- Positioned in header or sidebar.

### Story 6.8 – Responsive Design & Mobile
Ensure dashboard works on mobile devices.

**Acceptance Criteria**
- Grid collapses to single column on narrow screens.
- Charts resize appropriately.
- Text remains readable (min font size enforced).
- Test on mobile viewport (Chrome DevTools).
- No horizontal scroll required.

---

## Phase 7: LLM Integration (Stories 7.1–7.3)

### Story 7.1 – OpenRouter Client
Implement OpenRouter API client for LLM calls.

**Acceptance Criteria**
- Client supports OpenAI-compatible API with OpenRouter headers.
- Uses `openrouter/anthropic/claude-sonnet-4.5` model.
- Timeout and retry logic.
- Test mocks API response.
- API key loaded from environment, never logged.

### Story 7.2 – Explanation Generator
Generate human-readable explanations for signals.

**Acceptance Criteria**
- Function takes Signal + WeatherSnapshot + MarketSnapshot, returns explanation string.
- Prompt includes weather data, market odds, strategy decision.
- LLM output stored in analytics.signal_explanations table.
- Test verifies explanation generated (mocked LLM).
- Explanation never affects trading decision (advisory only).

### Story 7.3 – Anomaly Classifier
Use LLM to classify unusual market conditions.

**Acceptance Criteria**
- Detects anomalies: wide spread, low liquidity, forecast disagreement.
- LLM returns classification (NORMAL/SUSPICIOUS/ALERT) and reason.
- Stored in analytics.anomalies table.
- Test verifies classification logic (mocked LLM).
- Anomalies displayed in dashboard health section.

---

## Phase 8: Deployment & Operations (Stories 8.1–8.10)

### Story 8.1 – Systemd Service Files
Create systemd units for trader and analytics services.

**Acceptance Criteria**
- trader.service runs trading loop on schedule (cron-like or timer).
- analytics.service runs rollup jobs.
- dashboard.service runs Streamlit app.
- Auto-restart on failure.
- Test verifies services start and stop cleanly.

### Story 8.2 – NGINX Reverse Proxy Config
Configure NGINX to proxy Streamlit with WebSocket support.

**Acceptance Criteria**
- NGINX config proxies port 80/443 to Streamlit (default 8501).
- WebSocket headers included for live updates.
- SSL termination (cert placeholder).
- Test verifies dashboard accessible via domain.
- Only dashboard exposed; trader/analytics on localhost.

### Story 8.3 – Cloudflare DNS & Proxy
Configure Cloudflare for milkbot.ai domain.

**Acceptance Criteria**
- DNS A record points to VPS IP.
- Cloudflare proxy enabled (orange cloud).
- SSL mode: Full (strict).
- Test verifies HTTPS works.
- Firewall rules documented (allow only Cloudflare IPs).

### Story 8.4 – Database Backup & Restore
Implement automated Postgres backups.

**Acceptance Criteria**
- Daily pg_dump to local disk and S3/B2.
- Retention: 7 daily, 4 weekly, 12 monthly.
- Restore script tested with sample backup.
- Test verifies backup file created and valid.
- Backup excludes analytics schema (can be regenerated).

### Story 8.5 – Log Rotation & Retention
Configure log rotation for all services.

**Acceptance Criteria**
- Logs rotated daily, compressed after 1 day.
- Retention: 30 days local, 90 days archived.
- Separate logs per service (trader, analytics, dashboard).
- Test verifies rotation triggers.
- Logs parseable by standard tools (jq for JSON).

### Story 8.6 – Monitoring & Alerting (Healthchecks)
Set up external healthcheck monitoring.

**Acceptance Criteria**
- Healthcheck endpoint (HTTP) for each service.
- External monitor (e.g., UptimeRobot, Healthchecks.io) pings every 5 min.
- Alert via email/SMS if service down.
- Test verifies healthcheck returns 200 when healthy.
- Dashboard shows last healthcheck time.

### Story 8.7 – Secret Management
Implement secure secret storage and rotation.

**Acceptance Criteria**
- Secrets stored in environment variables or encrypted file.
- Never committed to git (.env in .gitignore).
- Rotation procedure documented.
- Test verifies secrets not in logs or error messages.
- Separate secrets for demo and live environments.

### Story 8.8 – Deployment Runbook
Document step-by-step deployment procedure.

**Acceptance Criteria**
- Runbook covers: initial setup, updates, rollback.
- Includes DB migration steps.
- Service restart order specified.
- Test verifies runbook by deploying to fresh VPS.
- Runbook in docs/DEPLOYMENT_RUNBOOK.md.

### Story 8.9 – Demo-to-Live Checklist
Create checklist for transitioning from demo to live trading.

**Acceptance Criteria**
- Checklist includes: API key swap, risk limit review, capital allocation, monitoring setup.
- Requires explicit confirmation (not automated).
- Test verifies demo mode cannot accidentally use live keys.
- Documented in docs/DEMO_TO_LIVE_PLAYBOOK.md.
- Includes rollback plan.

### Story 8.10 – Performance Tuning & Load Testing
Optimize critical queries and test under load.

**Acceptance Criteria**
- Dashboard queries profiled; slow queries optimized (indexes, query rewrite).
- Load test: 100 concurrent users on dashboard.
- Target: p95 response time < 500ms.
- Test verifies no crashes under load.
- Results documented with recommendations.

---

## Phase 9: Testing & Quality (Stories 9.1–9.4)

### Story 9.1 – Integration Test Suite
Create end-to-end integration tests.

**Acceptance Criteria**
- Test full trading cycle with mocked Kalshi and NWS.
- Verifies data flows from weather → signal → order → fill → analytics.
- Test reconciliation after simulated restart.
- All tests pass in CI environment.
- Coverage > 80% for critical paths.

### Story 9.2 – Performance Regression Tests
Create benchmark suite for critical operations.

**Acceptance Criteria**
- Benchmarks: DB queries, API calls, strategy evaluation.
- Baseline performance recorded.
- Test fails if regression > 20%.
- Runs in CI on every commit.
- Results tracked over time.

### Story 9.3 – Security Audit Checklist
Perform security review of codebase.

**Acceptance Criteria**
- Checklist covers: SQL injection, secret exposure, input validation, CSRF.
- No secrets in git history (verified with tool).
- Dashboard has no access to trading keys (verified by test).
- Test verifies public API cannot access ops schema.
- Findings documented and remediated.

### Story 9.4 – Chaos Testing (Failure Scenarios)
Test system behavior under failure conditions.

**Acceptance Criteria**
- Test scenarios: DB down, Kalshi API timeout, NWS API 500 error, disk full.
- Verifies graceful degradation (no crashes).
- Circuit breakers trigger appropriately.
- Test verifies trading pauses when data stale.
- Recovery procedure documented.

---

## Phase 10: Documentation & Handoff (Stories 10.1–10.3)

### Story 10.1 – API Documentation
Generate API docs for internal analytics API.

**Acceptance Criteria**
- OpenAPI/Swagger spec for all endpoints.
- Example requests and responses.
- Hosted at /docs endpoint.
- Test verifies spec is valid.
- Includes rate limits and error codes.

### Story 10.2 – Architecture Diagram
Create visual architecture diagram.

**Acceptance Criteria**
- Diagram shows: services, data flows, network boundaries.
- Includes Cloudflare, NGINX, Postgres, Streamlit.
- Highlights public vs. private components.
- Exported as PNG and editable source (e.g., draw.io).
- Included in README.md.

### Story 10.3 – Operator Runbook
Document common operational tasks.

**Acceptance Criteria**
- Runbook covers: restart services, check logs, manual reconciliation, emergency stop.
- Includes troubleshooting guide (common errors and fixes).
- Test verifies runbook by performing each task.
- Accessible to non-developers.
- Stored in docs/OPERATIONS_RUNBOOK.md.

---

**Total Stories: 60**
**Estimated Total Time: 60–120 hours (1–2 hours per story)**
