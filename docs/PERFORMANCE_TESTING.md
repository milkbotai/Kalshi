# Performance Testing Guide

## Overview

This guide covers performance testing procedures for the Milkbot platform, including query performance, load testing, and optimization strategies.

## Prerequisites

```bash
# Install testing dependencies
pip install pytest locust

# Ensure database is populated with test data
python scripts/generate_test_data.py
```

## Query Performance Testing

### Running Query Performance Tests

```bash
# Run all performance tests
pytest tests/performance/test_query_performance.py -v -s

# Run specific test
pytest tests/performance/test_query_performance.py::TestQueryPerformance::test_city_metrics_query_performance -v -s

# Run with profiling
pytest tests/performance/test_query_performance.py --profile
```

### Performance Targets

| Query Type | Target | Critical Threshold |
|------------|--------|-------------------|
| City Metrics | < 100ms | < 200ms |
| Equity Curve | < 50ms | < 100ms |
| Public Trades | < 50ms | < 100ms |
| Health Status | < 20ms | < 50ms |
| Strategy Metrics | < 100ms | < 200ms |

### Analyzing Slow Queries

```sql
-- Enable query logging
ALTER SYSTEM SET log_min_duration_statement = 100;
SELECT pg_reload_conf();

-- View slow queries
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    max_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 20;

-- Explain query plan
EXPLAIN ANALYZE
SELECT * FROM ops.trades WHERE created_at >= NOW() - INTERVAL '30 days';
```

## Load Testing

### Running Load Tests

```bash
# Basic load test (100 users, 5 minutes)
./deployment/scripts/run-load-test.sh

# Custom configuration
LOAD_TEST_HOST=http://localhost:8501 \
LOAD_TEST_USERS=200 \
LOAD_TEST_SPAWN_RATE=20 \
LOAD_TEST_RUN_TIME=10m \
./deployment/scripts/run-load-test.sh

# Interactive mode (with web UI)
locust -f tests/performance/locustfile.py --host=http://localhost:8501
# Then open http://localhost:8089
```

### Load Test Scenarios

#### Scenario 1: Normal Load
- **Users:** 50 concurrent
- **Duration:** 5 minutes
- **Expected:** All requests < 500ms P95

#### Scenario 2: Peak Load
- **Users:** 100 concurrent
- **Duration:** 10 minutes
- **Expected:** All requests < 1000ms P95

#### Scenario 3: Stress Test
- **Users:** 200 concurrent
- **Duration:** 15 minutes
- **Expected:** Identify breaking point

### Interpreting Results

Key metrics to monitor:

1. **Requests per Second (RPS)**
   - Target: > 50 RPS
   - Critical: < 20 RPS

2. **Response Times**
   - P50: < 200ms
   - P95: < 500ms
   - P99: < 1000ms

3. **Error Rate**
   - Target: < 0.1%
   - Critical: > 1%

4. **Resource Usage**
   - CPU: < 70%
   - Memory: < 80%
   - Database connections: < 80% of pool

## Database Optimization

### Running Optimization Script

```bash
# Run full optimization
./deployment/scripts/optimize-database.sh

# Manual optimization steps
psql -U milkbot -d milkbot

-- Create missing indexes
CREATE INDEX idx_trades_city_date ON ops.trades(city_code, created_at);

-- Analyze tables
ANALYZE ops.trades;

-- Vacuum tables
VACUUM ANALYZE ops.trades;
```

### Index Strategy

#### When to Add Indexes

- Columns used in WHERE clauses
- Columns used in JOIN conditions
- Columns used in ORDER BY
- Foreign key columns

#### When NOT to Add Indexes

- Small tables (< 1000 rows)
- Columns with low cardinality
- Frequently updated columns
- Tables with high write volume

### Query Optimization Techniques

1. **Use EXPLAIN ANALYZE**
   ```sql
   EXPLAIN ANALYZE
   SELECT * FROM ops.trades WHERE city_code = 'NYC';
   ```

2. **Add Covering Indexes**
   ```sql
   CREATE INDEX idx_trades_cover ON ops.trades(city_code, created_at, ticker, price);
   ```

3. **Use Partial Indexes**
   ```sql
   CREATE INDEX idx_trades_recent ON ops.trades(created_at) 
   WHERE created_at >= NOW() - INTERVAL '30 days';
   ```

4. **Optimize JOINs**
   ```sql
   -- Use INNER JOIN instead of subqueries
   SELECT t.*, m.ticker
   FROM ops.trades t
   INNER JOIN ops.markets m ON t.market_id = m.id;
   ```

## Application-Level Optimization

### Caching Strategy

1. **Query Result Caching**
   - Cache TTL: 5 seconds
   - Cache key: Include all query parameters
   - Invalidation: Time-based (no manual invalidation needed)

2. **Connection Pooling**
   ```python
   # Configure in settings
   SQLALCHEMY_POOL_SIZE = 20
   SQLALCHEMY_MAX_OVERFLOW = 10
   SQLALCHEMY_POOL_TIMEOUT = 30
   ```

3. **Lazy Loading**
   - Load data only when needed
   - Use pagination for large result sets
   - Implement infinite scroll for trade feed

### Code Profiling

```bash
# Profile Python code
python -m cProfile -o profile.stats src/dashboard/app.py

# Analyze profile
python -m pstats profile.stats
> sort cumulative
> stats 20

# Use line_profiler for detailed profiling
pip install line_profiler
kernprof -l -v src/analytics/api.py
```

## Continuous Performance Monitoring

### Setting Up Monitoring

1. **Query Performance Monitoring**
   ```sql
   -- Enable pg_stat_statements
   CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
   
   -- View query statistics
   SELECT * FROM pg_stat_statements ORDER BY mean_time DESC;
   ```

2. **Application Performance Monitoring**
   - Use structlog for timing logs
   - Track request duration
   - Monitor cache hit rates

3. **Infrastructure Monitoring**
   - CPU usage
   - Memory usage
   - Disk I/O
   - Network latency

### Performance Alerts

Set up alerts for:

- Query duration > 200ms (P95)
- Error rate > 1%
- CPU usage > 80%
- Memory usage > 90%
- Database connections > 80% of pool

## Performance Regression Testing

### Before Each Release

```bash
# 1. Run query performance tests
pytest tests/performance/test_query_performance.py -v

# 2. Run load tests
./deployment/scripts/run-load-test.sh

# 3. Compare results to baseline
diff tests/performance/results/baseline.txt tests/performance/results/current.txt

# 4. Update baseline if improved
cp tests/performance/results/current.txt tests/performance/results/baseline.txt
```

### Regression Criteria

Fail release if:

- Any query > 20% slower than baseline
- P95 response time > 20% slower
- Error rate increased by > 0.5%
- Memory usage increased by > 20%

## Troubleshooting Performance Issues

### Slow Queries

1. **Identify slow queries**
   ```sql
   SELECT query, mean_time, calls
   FROM pg_stat_statements
   WHERE mean_time > 100
   ORDER BY mean_time DESC;
   ```

2. **Analyze query plan**
   ```sql
   EXPLAIN ANALYZE <slow_query>;
   ```

3. **Add appropriate indexes**

4. **Rewrite query if needed**

### High CPU Usage

1. Check for missing indexes
2. Review query complexity
3. Check for N+1 query problems
4. Consider query result caching

### High Memory Usage

1. Check for memory leaks
2. Review cache size limits
3. Check connection pool size
4. Monitor Python object creation

### Database Connection Issues

1. Check connection pool configuration
2. Monitor active connections
3. Look for connection leaks
4. Review query timeout settings

## Best Practices

1. **Always test with production-like data volume**
2. **Run performance tests in CI/CD pipeline**
3. **Monitor performance in production continuously**
4. **Set up alerts for performance degradation**
5. **Document all optimizations and their impact**
6. **Review slow query logs weekly**
7. **Update performance baselines after optimizations**
8. **Test performance impact of schema changes**

## Resources

- [PostgreSQL Performance Tuning](https://wiki.postgresql.org/wiki/Performance_Optimization)
- [Locust Documentation](https://docs.locust.io/)
- [SQLAlchemy Performance Tips](https://docs.sqlalchemy.org/en/14/faq/performance.html)
- [Streamlit Performance](https://docs.streamlit.io/library/advanced-features/caching)
