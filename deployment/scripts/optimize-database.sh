#!/bin/bash
# Database optimization script

set -euo pipefail

DB_NAME="${POSTGRES_DB:-milkbot}"
DB_USER="${POSTGRES_USER:-milkbot}"

echo "Starting database optimization..."

# Create indexes for common queries
echo "Creating indexes..."
psql -U "$DB_USER" -d "$DB_NAME" << 'EOF'
-- Trades table indexes
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON ops.trades(created_at);
CREATE INDEX IF NOT EXISTS idx_trades_city_code ON ops.trades(city_code);
CREATE INDEX IF NOT EXISTS idx_trades_ticker ON ops.trades(ticker);
CREATE INDEX IF NOT EXISTS idx_trades_city_date ON ops.trades(city_code, created_at);

-- Signals table indexes
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON ops.signals(created_at);
CREATE INDEX IF NOT EXISTS idx_signals_strategy ON ops.signals(strategy_name);
CREATE INDEX IF NOT EXISTS idx_signals_city ON ops.signals(city_code);
CREATE INDEX IF NOT EXISTS idx_signals_strategy_date ON ops.signals(strategy_name, created_at);

-- Orders table indexes
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON ops.orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_status ON ops.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_intent_key ON ops.orders(intent_key);

-- Fills table indexes
CREATE INDEX IF NOT EXISTS idx_fills_created_at ON ops.fills(created_at);
CREATE INDEX IF NOT EXISTS idx_fills_order_id ON ops.fills(order_id);

-- Positions table indexes
CREATE INDEX IF NOT EXISTS idx_positions_market_id ON ops.positions(market_id);
CREATE INDEX IF NOT EXISTS idx_positions_status ON ops.positions(status);

-- Weather snapshots indexes
CREATE INDEX IF NOT EXISTS idx_weather_city_captured ON ops.weather_snapshots(city_code, captured_at);

-- Market snapshots indexes
CREATE INDEX IF NOT EXISTS idx_market_ticker_captured ON ops.market_snapshots(ticker, captured_at);

-- Analytics indexes
CREATE INDEX IF NOT EXISTS idx_equity_curve_date ON analytics.equity_curve(date);
CREATE INDEX IF NOT EXISTS idx_city_metrics_city_date ON analytics.city_metrics(city_code, date);
CREATE INDEX IF NOT EXISTS idx_strategy_metrics_strategy_date ON analytics.strategy_metrics(strategy_name, date);

-- Health status indexes
CREATE INDEX IF NOT EXISTS idx_health_component ON ops.health_status(component);
CREATE INDEX IF NOT EXISTS idx_health_updated ON ops.health_status(updated_at);
EOF

echo "Indexes created successfully"

# Analyze tables for query planner
echo "Analyzing tables..."
psql -U "$DB_USER" -d "$DB_NAME" << 'EOF'
ANALYZE ops.trades;
ANALYZE ops.signals;
ANALYZE ops.orders;
ANALYZE ops.fills;
ANALYZE ops.positions;
ANALYZE ops.weather_snapshots;
ANALYZE ops.market_snapshots;
ANALYZE analytics.equity_curve;
ANALYZE analytics.city_metrics;
ANALYZE analytics.strategy_metrics;
EOF

echo "Analysis complete"

# Vacuum tables
echo "Vacuuming tables..."
psql -U "$DB_USER" -d "$DB_NAME" << 'EOF'
VACUUM ANALYZE ops.trades;
VACUUM ANALYZE ops.signals;
VACUUM ANALYZE ops.orders;
VACUUM ANALYZE ops.fills;
VACUUM ANALYZE ops.positions;
EOF

echo "Vacuum complete"

# Show table sizes
echo ""
echo "Table sizes:"
psql -U "$DB_USER" -d "$DB_NAME" << 'EOF'
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname IN ('ops', 'analytics')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
EOF

# Show index usage
echo ""
echo "Index usage statistics:"
psql -U "$DB_USER" -d "$DB_NAME" << 'EOF'
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan as scans,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE schemaname IN ('ops', 'analytics')
ORDER BY idx_scan DESC
LIMIT 20;
EOF

echo ""
echo "Database optimization complete!"
echo ""
echo "Next steps:"
echo "1. Run performance tests to measure improvement"
echo "2. Monitor query performance in production"
echo "3. Review slow query logs regularly"
