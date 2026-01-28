-- Migration 002: Create analytics.v_public_trades view
-- Implements 60-minute delayed trade disclosure per public disclosure policy

-- Drop view if exists (for re-running migrations)
DROP VIEW IF EXISTS analytics.v_public_trades;

-- Create the public trades view with 60-minute delay
-- Redacts: order_id, intent_key, raw payloads, client-sensitive data
CREATE VIEW analytics.v_public_trades AS
SELECT
    -- Trade identification (anonymized)
    t.id AS trade_id,

    -- Market context
    m.ticker,
    m.city_code,
    m.market_type,
    m.title AS market_title,

    -- Trade details (public)
    t.side,
    t.action,
    t.quantity,
    t.price,
    t.fees,
    t.total_cost,

    -- P&L (when position is closed)
    t.realized_pnl,

    -- Timing (rounded to minute for privacy)
    date_trunc('minute', t.executed_at) AS trade_time,

    -- Strategy (public, for transparency)
    t.strategy_name

FROM trades t
JOIN markets m ON t.market_id = m.id

-- CRITICAL: 60-minute delay filter
-- This is the core privacy protection mandated by PUBLIC_TRADE_DELAY_MIN=60
WHERE t.executed_at <= (NOW() - INTERVAL '60 minutes')

-- Sorted by time descending (most recent delayed trades first)
ORDER BY t.executed_at DESC;

-- Add comment explaining the view
COMMENT ON VIEW analytics.v_public_trades IS
    'Public trade feed with mandatory 60-minute delay. '
    'Redacts order IDs, intent keys, and raw payloads. '
    'Trade times rounded to minute for additional privacy.';
