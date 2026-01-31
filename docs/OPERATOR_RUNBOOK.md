# Operator Runbook

**Document Version:** 1.0
**Last Updated:** 2026-01-29

## Quick Reference

| Action | Command |
|--------|---------|
| Check all services | `systemctl status milkbot-*` |
| View trader logs | `journalctl -u milkbot-trader -f` |
| Emergency stop | `systemctl stop milkbot-trader.timer` |
| Restart all | `systemctl restart milkbot-{analytics,dashboard}` |
| Health check | `/opt/milkbot/deployment/scripts/healthcheck.sh` |
| Database backup | `/opt/milkbot/deployment/scripts/backup-database.sh daily` |

---

## 1. Service Management

### 1.1 Service Status

Check status of all Milkbot services:

```bash
# All services
systemctl status milkbot-trader.timer
systemctl status milkbot-analytics.service
systemctl status milkbot-dashboard.service
systemctl status milkbot-rollups.timer

# Quick status check
systemctl is-active milkbot-{trader,analytics,dashboard}.service
```

### 1.2 Start/Stop/Restart Services

```bash
# Start all services (recommended order)
systemctl start milkbot-analytics.service
systemctl start milkbot-dashboard.service
systemctl start milkbot-trader.timer

# Stop all services
systemctl stop milkbot-trader.timer
systemctl stop milkbot-dashboard.service
systemctl stop milkbot-analytics.service

# Restart individual service
systemctl restart milkbot-analytics.service

# Reload configuration (no restart)
systemctl reload milkbot-analytics.service
```

### 1.3 View Logs

```bash
# Real-time trader logs
journalctl -u milkbot-trader.service -f

# Last 100 lines of analytics logs
journalctl -u milkbot-analytics.service -n 100

# Errors only
journalctl -u milkbot-trader.service -p err

# Logs from specific time
journalctl -u milkbot-trader.service --since "1 hour ago"

# JSON log files (alternative)
tail -f /var/log/milkbot/trader.log | jq .
```

---

## 2. Emergency Procedures

### 2.1 Emergency Stop (Kill Switch)

**When to use:** Runaway orders, unexpected behavior, risk breach

```bash
# IMMEDIATE STOP - prevents new trading cycles
systemctl stop milkbot-trader.timer
systemctl stop milkbot-trader.service

# Verify stopped
systemctl is-active milkbot-trader.timer  # Should say "inactive"

# Check for any running processes
pgrep -f "trading_loop"
```

### 2.2 Circuit Breaker Manual Reset

If circuit breaker triggered and you need to resume trading:

```bash
# Check circuit breaker status
cd /opt/milkbot
./venv/bin/python -c "
from src.trader.risk import RiskCalculator
calc = RiskCalculator()
print('Circuit breaker active:', calc.is_circuit_breaker_triggered())
print('Daily loss:', calc.get_daily_pnl())
"

# Manual reset (use with caution!)
./venv/bin/python -c "
from src.trader.risk import RiskCalculator
calc = RiskCalculator()
calc.reset_circuit_breaker()
print('Circuit breaker reset')
"
```

### 2.3 Position Liquidation

**When to use:** Need to close all positions immediately

```bash
# View current positions
cd /opt/milkbot
./venv/bin/python -c "
from src.trader.oms import OrderManagementSystem
oms = OrderManagementSystem()
for pos in oms.get_open_positions():
    print(f'{pos.ticker}: {pos.quantity} @ {pos.avg_price}')
"

# Cancel all pending orders
./venv/bin/python -c "
from src.trader.oms import OrderManagementSystem
oms = OrderManagementSystem()
cancelled = oms.cancel_all_pending()
print(f'Cancelled {cancelled} orders')
"
```

---

## 3. Health Monitoring

### 3.1 Health Check Script

```bash
# Full health check
/opt/milkbot/deployment/scripts/healthcheck.sh

# Health check with alerting
/opt/milkbot/deployment/scripts/healthcheck.sh --alert
```

### 3.2 Component Health

```bash
# Database connectivity
pg_isready -h localhost -d milkbot -U milkbot

# Analytics API
curl -s http://127.0.0.1:8000/v1/health | jq .

# Dashboard
curl -s http://127.0.0.1:8501/_stcore/health

# NGINX
systemctl status nginx
nginx -t  # Config test
```

### 3.3 Resource Monitoring

```bash
# Memory usage
free -h
ps aux --sort=-%mem | head -10

# Disk usage
df -h /opt/milkbot
du -sh /var/log/milkbot/*

# Database size
psql -U milkbot -d milkbot -c "
SELECT pg_size_pretty(pg_database_size('milkbot'));
"

# Connection count
psql -U milkbot -d milkbot -c "
SELECT count(*) FROM pg_stat_activity WHERE datname = 'milkbot';
"
```

---

## 4. Database Operations

### 4.1 Backup

```bash
# Daily backup
/opt/milkbot/deployment/scripts/backup-database.sh daily

# Weekly backup
/opt/milkbot/deployment/scripts/backup-database.sh weekly

# Manual backup with custom name
pg_dump -h localhost -U milkbot milkbot | gzip > /var/backups/milkbot/manual_$(date +%Y%m%d).sql.gz
```

### 4.2 Restore

```bash
# List available backups
ls -la /var/backups/milkbot/*/

# Restore from backup (DESTRUCTIVE!)
/opt/milkbot/deployment/scripts/restore-database.sh /var/backups/milkbot/daily/milkbot_20260129_010000.sql.gz
```

### 4.3 Database Queries

```bash
# Connect to database
psql -U milkbot -d milkbot

# Recent trades
psql -U milkbot -d milkbot -c "
SELECT * FROM ops.orders
ORDER BY created_at DESC
LIMIT 10;
"

# Today's P&L
psql -U milkbot -d milkbot -c "
SELECT SUM(pnl) as daily_pnl
FROM ops.fills
WHERE fill_time >= CURRENT_DATE;
"

# Check public trade delay
psql -U milkbot -d milkbot -c "
SELECT * FROM analytics.v_public_trades
ORDER BY fill_time DESC
LIMIT 5;
"
```

### 4.4 Database Optimization

```bash
# Run optimization (indexes, vacuum)
/opt/milkbot/deployment/scripts/optimize-database.sh

# Manual vacuum
psql -U milkbot -d milkbot -c "VACUUM ANALYZE;"
```

---

## 5. Troubleshooting

### 5.1 Service Won't Start

```bash
# Check for configuration errors
journalctl -u milkbot-analytics.service -n 50

# Verify environment file
cat /opt/milkbot/.env | grep -v PASSWORD

# Check file permissions
ls -la /opt/milkbot/
ls -la /var/log/milkbot/

# Test Python imports
cd /opt/milkbot
./venv/bin/python -c "from src.trader.trading_loop import TradingLoop; print('OK')"
```

### 5.2 Database Connection Issues

```bash
# Check PostgreSQL is running
systemctl status postgresql

# Check connection
pg_isready -h localhost -d milkbot -U milkbot

# Check pg_hba.conf
sudo cat /etc/postgresql/*/main/pg_hba.conf | grep milkbot

# Reset connections
psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'milkbot' AND pid <> pg_backend_pid();"
```

### 5.3 API Errors

```bash
# Check Kalshi API connectivity
cd /opt/milkbot
./venv/bin/python -c "
from src.shared.api.kalshi import KalshiClient
client = KalshiClient()
print('Auth:', client.authenticate())
"

# Check NWS API
curl -s "https://api.weather.gov/points/40.7128,-74.0060" | jq .properties.gridId

# Check rate limiting
grep "429" /var/log/milkbot/trader.log | tail -10
```

### 5.4 High Memory Usage

```bash
# Find memory hogs
ps aux --sort=-%mem | head -10

# Restart services to free memory
systemctl restart milkbot-analytics.service

# Clear Python cache
find /opt/milkbot -name "*.pyc" -delete
find /opt/milkbot -name "__pycache__" -type d -exec rm -rf {} +
```

### 5.5 Disk Full

```bash
# Find large files
du -sh /var/log/milkbot/*
du -sh /var/backups/milkbot/*

# Force log rotation
logrotate -f /etc/logrotate.d/milkbot

# Clean old backups
find /var/backups/milkbot/daily -mtime +7 -delete
```

---

## 6. Common Tasks

### 6.1 View Recent Trading Activity

```bash
# Last 10 signals
psql -U milkbot -d milkbot -c "
SELECT ticker, side, confidence, reason, created_at
FROM ops.signals
ORDER BY created_at DESC
LIMIT 10;
"

# Last 10 orders
psql -U milkbot -d milkbot -c "
SELECT ticker, side, quantity, limit_price, status, created_at
FROM ops.orders
ORDER BY created_at DESC
LIMIT 10;
"

# Today's summary
psql -U milkbot -d milkbot -c "
SELECT
    COUNT(*) as trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
    SUM(pnl) as total_pnl
FROM ops.fills
WHERE fill_time >= CURRENT_DATE;
"
```

### 6.2 Check Market Status

```bash
cd /opt/milkbot
./venv/bin/python -c "
from src.shared.api.kalshi import KalshiClient
from src.shared.config.cities import load_cities

client = KalshiClient()
cities = load_cities()

for code, city in list(cities.items())[:3]:
    markets = client.get_markets(f'HIGH{code}')
    print(f'{code}: {len(markets)} markets')
"
```

### 6.3 Manual Reconciliation

```bash
cd /opt/milkbot
./venv/bin/python -c "
from src.trader.oms import OrderManagementSystem
oms = OrderManagementSystem()
result = oms.reconcile()
print(f'Reconciled: {result}')
"
```

### 6.4 Run Analytics Rollups Manually

```bash
cd /opt/milkbot
./venv/bin/python -c "
from src.analytics.rollups import run_daily_rollups
run_daily_rollups()
print('Rollups complete')
"
```

---

## 7. Escalation Paths

### 7.1 Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| P1 | Service down, trading halted | Immediate | All services down, database unreachable |
| P2 | Degraded service | 15 minutes | Single service down, high error rate |
| P3 | Minor issue | 1 hour | Slow queries, warning logs |
| P4 | Informational | Next business day | Feature requests, optimizations |

### 7.2 Escalation Contacts

| Role | Contact | When to Escalate |
|------|---------|------------------|
| On-call Operator | [Contact Info] | P1/P2 issues |
| Engineering Lead | [Contact Info] | P1 unresolved > 30 min |
| Infrastructure | [Contact Info] | Server/network issues |

### 7.3 External Dependencies

| Service | Status Page | Support Contact |
|---------|-------------|-----------------|
| Kalshi | status.kalshi.com | support@kalshi.com |
| NWS | weather.gov/status | N/A (government) |
| Cloudflare | cloudflarestatus.com | Support dashboard |

---

## 8. Scheduled Maintenance

### 8.1 Daily Tasks (Automated)

- 01:00 ET: Analytics rollups (milkbot-rollups.timer)
- 02:00 ET: Database backup (cron)
- 03:00 ET: Log rotation (logrotate)

### 8.2 Weekly Tasks

- [ ] Review error logs
- [ ] Check disk usage
- [ ] Verify backups completed
- [ ] Review P&L and metrics

### 8.3 Monthly Tasks

- [ ] Run database optimization
- [ ] Review and rotate API keys if needed
- [ ] Update dependencies (security patches)
- [ ] Review security audit checklist

---

## 9. Recovery Procedures

### 9.1 Full System Recovery

1. Verify VPS is accessible
2. Start PostgreSQL: `systemctl start postgresql`
3. Verify database: `pg_isready -d milkbot`
4. Start Analytics: `systemctl start milkbot-analytics.service`
5. Verify API: `curl http://127.0.0.1:8000/v1/health`
6. Start Dashboard: `systemctl start milkbot-dashboard.service`
7. Verify Dashboard: `curl http://127.0.0.1:8501/_stcore/health`
8. Start Trader: `systemctl start milkbot-trader.timer`
9. Monitor logs: `journalctl -u milkbot-trader.service -f`

### 9.2 Disaster Recovery

1. Provision new VPS
2. Install dependencies (see DEPLOYMENT_RUNBOOK)
3. Restore database from S3 backup
4. Copy `.env` from secure storage
5. Follow Full System Recovery steps
6. Verify trading reconciliation

---

## Appendix: Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TRADING_MODE` | shadow/demo/live | Yes |
| `KALSHI_API_KEY` | Kalshi API key | Yes |
| `KALSHI_API_SECRET` | Kalshi API secret | Yes |
| `DATABASE_URL` | PostgreSQL connection | Yes |
| `OPENROUTER_API_KEY` | LLM API key | No |
| `MILKBOT_SLACK_WEBHOOK` | Alert webhook | No |
| `MILKBOT_HEALTHCHECKS_URL` | Healthchecks.io URL | No |
