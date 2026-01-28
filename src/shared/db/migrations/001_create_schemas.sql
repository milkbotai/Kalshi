-- Migration 001: Create ops and analytics schemas
-- Creates the two-schema architecture for data isolation

-- Create ops schema (if not exists)
CREATE SCHEMA IF NOT EXISTS ops;

-- Create analytics schema
CREATE SCHEMA IF NOT EXISTS analytics;

-- Grant usage on analytics schema to public (for dashboard access)
-- Note: In production, use a specific read-only role instead
COMMENT ON SCHEMA ops IS 'Private operational data - trading engine only';
COMMENT ON SCHEMA analytics IS 'Sanitized views and rollups for public dashboard';
