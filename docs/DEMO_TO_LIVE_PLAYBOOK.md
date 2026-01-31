# Demo to Live Trading Playbook

**Document Version:** 1.0
**Last Updated:** 2026-01-30

This playbook provides a structured checklist for transitioning Milkbot from demo trading to live trading on Kalshi. Follow each section in order and verify all checkpoints before proceeding.

---

## Table of Contents

1. [Pre-Transition Requirements](#1-pre-transition-requirements)
2. [Risk Limit Verification](#2-risk-limit-verification)
3. [Capital Allocation Confirmation](#3-capital-allocation-confirmation)
4. [API Key Swap Procedure](#4-api-key-swap-procedure)
5. [Go-Live Checklist](#5-go-live-checklist)
6. [Post-Go-Live Monitoring](#6-post-go-live-monitoring)
7. [Rollback Plan](#7-rollback-plan)
8. [Emergency Procedures](#8-emergency-procedures)

---

## 1. Pre-Transition Requirements

### 1.1 Demo Period Completion

Before transitioning to live trading, the system must have completed a successful demo period:

**Minimum Requirements:**
- [ ] **10 consecutive days** of demo trading without critical errors
- [ ] **72+ hours** of continuous operation without restarts (per MVP acceptance criteria)
- [ ] **Zero duplicate orders** from restarts or race conditions
- [ ] **Zero unhandled exceptions** in steady-state operation

**Performance Metrics:**
- [ ] Circuit breakers triggered correctly when limits were hit
- [ ] All risk limits were respected (daily/weekly/monthly)
- [ ] Execution quality metrics captured (spread, slippage, fill rate)
- [ ] Forecast edge tracking shows positive expected value

### 1.2 Demo Period Sign-Off

| Checkpoint | Date Verified | Verified By |
|------------|---------------|-------------|
| 10-day demo completed | _____________ | _____________ |
| No critical errors | _____________ | _____________ |
| Risk limits respected | _____________ | _____________ |
| Performance acceptable | _____________ | _____________ |

**Sign-off:**

```
I confirm that the demo period requirements have been met and the system
is ready to transition to live trading.

Name: _______________________
Date: _______________________
Signature: __________________
```

---

## 2. Risk Limit Verification

### 2.1 Review Current Risk Configuration

Before going live, verify all risk limits are appropriate for live trading:

```bash
# Display current risk configuration
cat /opt/milkbot/.env | grep -E "^(BANKROLL|MAX_|SPREAD_|LIQUIDITY_|MIN_EDGE)"
```

### 2.2 Risk Limit Checklist

**Portfolio Caps (verify values match your risk tolerance):**

| Parameter | Demo Value | Live Value | Verified |
|-----------|------------|------------|----------|
| `BANKROLL` | $5,000 | $_________ | [ ] |
| `MAX_OPEN_RISK_PCT` | 10% | _________% | [ ] |
| `MAX_DAILY_LOSS_PCT` | 5% | _________% | [ ] |
| `MAX_WEEKLY_LOSS_PCT` | 12% | _________% | [ ] |
| `MAX_MONTHLY_LOSS_PCT` | 20% | _________% | [ ] |

**Per-Trade Caps:**

| Parameter | Demo Value | Live Value | Verified |
|-----------|------------|------------|----------|
| `MAX_TRADE_RISK_PCT` | 2% | _________% | [ ] |
| `MAX_CITY_EXPOSURE_PCT` | 3% | _________% | [ ] |
| `MAX_CLUSTER_EXPOSURE_PCT` | 5% | _________% | [ ] |

**Execution Gates:**

| Parameter | Demo Value | Live Value | Verified |
|-----------|------------|------------|----------|
| `SPREAD_MAX_CENTS` | 3 | _________ | [ ] |
| `LIQUIDITY_MIN` | 500 | _________ | [ ] |
| `MIN_EDGE_AFTER_COSTS` | 2% | _________% | [ ] |

### 2.3 Calculate Dollar Amounts

With your live bankroll, verify the dollar amounts:

```
Live Bankroll:           $__________

Max Open Risk (10%):     $__________
Max Daily Loss (5%):     $__________
Max Weekly Loss (12%):   $__________
Max Monthly Loss (20%):  $__________
Max Per-Trade (2%):      $__________
Max Per-City (3%):       $__________
Max Per-Cluster (5%):    $__________
```

**Risk Limit Sign-off:**

- [ ] I have reviewed all risk limits
- [ ] Dollar amounts are acceptable for my risk tolerance
- [ ] Circuit breaker thresholds are appropriate

---

## 3. Capital Allocation Confirmation

### 3.1 Kalshi Account Verification

Before going live, verify your Kalshi account:

- [ ] **Live Kalshi account exists** and is verified
- [ ] **Account in good standing** (no restrictions)
- [ ] **API access enabled** on live account
- [ ] **2FA enabled** for account security

### 3.2 Capital Funding

| Item | Amount | Verified |
|------|--------|----------|
| Kalshi account balance | $_________ | [ ] |
| Configured bankroll | $_________ | [ ] |
| Buffer (recommended 20% extra) | $_________ | [ ] |

**Important:** Your Kalshi account balance should be at least 120% of your configured bankroll to handle temporary drawdowns and ensure orders can always be placed.

### 3.3 Withdrawal/Deposit Plan

Document your capital management plan:

- **Initial deposit:** $__________
- **Profit withdrawal threshold:** $___________ (when to withdraw profits)
- **Loss replenishment plan:** How will you handle significant drawdowns?

```
Capital Management Notes:
_________________________________________________________________
_________________________________________________________________
_________________________________________________________________
```

### 3.4 Capital Confirmation Sign-off

- [ ] Kalshi account is funded with sufficient capital
- [ ] Account balance >= 120% of configured bankroll
- [ ] Capital management plan documented

---

## 4. API Key Swap Procedure

### 4.1 Pre-Swap Preparation

**1. Stop all trading activity:**

```bash
# Stop trader (prevents new orders)
sudo systemctl stop milkbot-trader.timer
sudo systemctl stop milkbot-trader.service

# Verify stopped
systemctl is-active milkbot-trader.timer  # Should say "inactive"
```

**2. Verify no pending orders:**

```bash
cd /opt/milkbot
source venv/bin/activate
python -c "
from src.trader.oms import OrderManagementSystem
oms = OrderManagementSystem()
pending = oms.get_pending_orders()
print(f'Pending orders: {len(pending)}')
for order in pending:
    print(f'  {order.ticker}: {order.side} {order.quantity}')
"
```

- [ ] No pending orders (or all cancelled)

**3. Create backup:**

```bash
/opt/milkbot/deployment/scripts/backup-database.sh daily
cp /opt/milkbot/.env /opt/milkbot/.env.demo.backup
```

### 4.2 Update Environment File

**1. Open environment file:**

```bash
sudo nano /opt/milkbot/.env
```

**2. Update the following values:**

```bash
# BEFORE (Demo)
TRADING_MODE=demo
KALSHI_API_BASE=https://demo-api.kalshi.co/trade-api/v2
KALSHI_EMAIL=demo@example.com
KALSHI_PASSWORD=demo_password
KALSHI_MEMBER_ID=

# AFTER (Live)
TRADING_MODE=live
KALSHI_API_BASE=https://trading-api.kalshi.com/trade-api/v2
KALSHI_EMAIL=your_live_email@example.com
KALSHI_PASSWORD=your_live_password
KALSHI_MEMBER_ID=your_member_id
```

**3. Update risk limits (if different for live):**

```bash
# Adjust as needed for live trading
BANKROLL=YOUR_LIVE_BANKROLL
```

**4. Save and secure:**

```bash
chmod 600 /opt/milkbot/.env
```

### 4.3 API Key Verification

**Verify live credentials work before starting services:**

```bash
cd /opt/milkbot
source venv/bin/activate

python -c "
from src.shared.api.kalshi import KalshiClient
from src.shared.config.settings import get_settings

settings = get_settings()
print(f'Trading Mode: {settings.trading_mode}')
print(f'API Base: {settings.kalshi_api_url}')

client = KalshiClient()
auth = client.authenticate()
print(f'Authentication: {\"SUCCESS\" if auth else \"FAILED\"}')

# Get account balance
balance = client.get_balance()
print(f'Account Balance: \${balance}')
"
```

- [ ] Trading mode shows "live"
- [ ] API base is production URL
- [ ] Authentication successful
- [ ] Account balance correct

### 4.4 API Swap Checklist

| Step | Completed |
|------|-----------|
| Trader service stopped | [ ] |
| No pending orders | [ ] |
| Database backed up | [ ] |
| .env backed up | [ ] |
| TRADING_MODE changed to "live" | [ ] |
| API base URL updated | [ ] |
| Live credentials entered | [ ] |
| File permissions secured (600) | [ ] |
| Credentials verified working | [ ] |

---

## 5. Go-Live Checklist

### 5.1 Final Pre-Launch Verification

Before starting live trading, complete this final checklist:

**System Health:**
- [ ] All services healthy: `/opt/milkbot/deployment/scripts/healthcheck.sh`
- [ ] Database accessible and backed up
- [ ] Sufficient disk space (>10GB free)
- [ ] Memory usage normal (<80%)

**Configuration:**
- [ ] `TRADING_MODE=live` confirmed
- [ ] Live API credentials verified
- [ ] Risk limits reviewed and confirmed
- [ ] Bankroll matches account balance

**External Dependencies:**
- [ ] Kalshi API accessible
- [ ] NWS API accessible
- [ ] Network connectivity stable

### 5.2 Start Live Trading

```bash
# Start services in order
sudo systemctl start milkbot-analytics.service
sleep 5

# Verify analytics
curl -s http://127.0.0.1:8000/v1/health | jq .

# Start dashboard
sudo systemctl start milkbot-dashboard.service
sleep 10

# Verify dashboard
curl -s http://127.0.0.1:8501/_stcore/health

# START LIVE TRADING
sudo systemctl start milkbot-trader.timer

# Verify trader is scheduled
systemctl status milkbot-trader.timer
```

### 5.3 First Trade Verification

**Monitor the first trading cycle closely:**

```bash
# Watch trader logs in real-time
journalctl -u milkbot-trader.service -f
```

After the first cycle completes:

- [ ] No errors in logs
- [ ] Signals generated (if market conditions warrant)
- [ ] Risk checks passed
- [ ] Orders placed (if signals generated)
- [ ] Fills recorded correctly

### 5.4 Go-Live Sign-off

```
LIVE TRADING ACTIVATED

Date/Time: _______________________
Activated By: ____________________

Initial State:
- Account Balance: $______________
- Configured Bankroll: $__________
- Open Positions: ________________

Notes:
_________________________________________________________________
_________________________________________________________________
```

---

## 6. Post-Go-Live Monitoring

### 6.1 First 24 Hours

During the first 24 hours of live trading, monitor closely:

**Every Hour:**
- [ ] Check service status: `systemctl status milkbot-trader.timer`
- [ ] Review error logs: `journalctl -u milkbot-trader -p err --since "1 hour ago"`
- [ ] Verify no circuit breaker triggers

**Every 4 Hours:**
- [ ] Check P&L and positions via dashboard
- [ ] Verify orders are filling correctly
- [ ] Compare to expected demo behavior

### 6.2 First Week Monitoring

| Day | Services OK | No Errors | P&L Tracking | Risk Limits OK | Notes |
|-----|-------------|-----------|--------------|----------------|-------|
| 1 | [ ] | [ ] | [ ] | [ ] | |
| 2 | [ ] | [ ] | [ ] | [ ] | |
| 3 | [ ] | [ ] | [ ] | [ ] | |
| 4 | [ ] | [ ] | [ ] | [ ] | |
| 5 | [ ] | [ ] | [ ] | [ ] | |
| 6 | [ ] | [ ] | [ ] | [ ] | |
| 7 | [ ] | [ ] | [ ] | [ ] | |

### 6.3 Ongoing Monitoring Checklist

**Daily:**
- [ ] Review daily P&L
- [ ] Check for any error logs
- [ ] Verify backups completed

**Weekly:**
- [ ] Review weekly performance
- [ ] Check risk limit utilization
- [ ] Verify forecast edge is positive
- [ ] Review and archive logs

**Monthly:**
- [ ] Full performance review
- [ ] Risk limit adjustment if needed
- [ ] System maintenance window

---

## 7. Rollback Plan

### 7.1 When to Rollback

Immediately rollback to demo if any of these occur:

- **Critical errors:** Unhandled exceptions, service crashes
- **Risk breach:** Limits exceeded without circuit breaker trigger
- **Order issues:** Duplicate orders, incorrect fills, reconciliation failures
- **Capital loss:** Unexpected rapid loss exceeding thresholds
- **API issues:** Authentication failures, rate limiting, unexpected responses

### 7.2 Immediate Rollback Procedure

**Step 1: Stop Trading Immediately**

```bash
# EMERGENCY STOP
sudo systemctl stop milkbot-trader.timer
sudo systemctl stop milkbot-trader.service

# Verify stopped
pgrep -f "trading_loop" && echo "WARNING: Process still running!"
```

**Step 2: Cancel Any Pending Orders**

```bash
cd /opt/milkbot
source venv/bin/activate

python -c "
from src.trader.oms import OrderManagementSystem
oms = OrderManagementSystem()
cancelled = oms.cancel_all_pending()
print(f'Cancelled {cancelled} orders')
"
```

**Step 3: Restore Demo Configuration**

```bash
# Restore demo .env
cp /opt/milkbot/.env.demo.backup /opt/milkbot/.env

# Or manually update
sudo nano /opt/milkbot/.env
# Change TRADING_MODE=demo
# Change API base back to demo
```

**Step 4: Restart in Demo Mode**

```bash
sudo systemctl start milkbot-analytics.service
sudo systemctl start milkbot-dashboard.service
sudo systemctl start milkbot-trader.timer

# Verify demo mode
cd /opt/milkbot
source venv/bin/activate
python -c "from src.shared.config.settings import get_settings; print(get_settings().trading_mode)"
```

### 7.3 Rollback Checklist

| Step | Completed | Time |
|------|-----------|------|
| Trader stopped | [ ] | ___:___ |
| Pending orders cancelled | [ ] | ___:___ |
| .env restored to demo | [ ] | ___:___ |
| Services restarted | [ ] | ___:___ |
| Demo mode verified | [ ] | ___:___ |
| Incident documented | [ ] | ___:___ |

### 7.4 Post-Rollback Actions

After rolling back:

1. **Document the incident:**
   - What happened?
   - What was the impact?
   - Root cause (if known)

2. **Review logs:**
   ```bash
   journalctl -u milkbot-trader --since "2 hours ago" > incident_logs.txt
   ```

3. **Assess damage:**
   - Check Kalshi account for actual positions
   - Calculate any realized losses
   - Verify database consistency

4. **Plan remediation:**
   - Fix the root cause
   - Add additional safeguards
   - Plan re-transition timeline

---

## 8. Emergency Procedures

### 8.1 Emergency Contacts

| Role | Contact | When to Call |
|------|---------|--------------|
| Primary Operator | _____________ | Any P1/P2 issue |
| Backup Operator | _____________ | Primary unavailable |
| Kalshi Support | support@kalshi.com | Account issues |

### 8.2 Emergency Kill Switch

If you need to stop ALL trading activity immediately:

```bash
#!/bin/bash
# EMERGENCY KILL SWITCH

echo "!!! EMERGENCY KILL SWITCH ACTIVATED !!!"
echo "Stopping all trading activity..."

# Stop trader
sudo systemctl stop milkbot-trader.timer
sudo systemctl stop milkbot-trader.service

# Cancel all orders
cd /opt/milkbot
source venv/bin/activate
python -c "
from src.trader.oms import OrderManagementSystem
oms = OrderManagementSystem()
oms.cancel_all_pending()
print('All pending orders cancelled')
"

echo "Trading stopped. Review positions manually at kalshi.com"
```

### 8.3 Manual Position Closure

If you need to close all positions manually:

1. Log into kalshi.com directly
2. Navigate to Positions
3. Close each position manually
4. Document all manual actions

**Do NOT rely on automated systems during emergencies.**

### 8.4 Incident Response Template

```
INCIDENT REPORT

Date/Time Detected: _______________
Date/Time Resolved: _______________
Severity: P1 / P2 / P3

Summary:
_________________________________________________________________

Impact:
- Financial: $_________
- Positions affected: ___
- Duration: ___ minutes

Root Cause:
_________________________________________________________________

Actions Taken:
1. _______________________________________________________________
2. _______________________________________________________________
3. _______________________________________________________________

Preventive Measures:
_________________________________________________________________

Reported By: _________________
Reviewed By: _________________
```

---

## Appendix: Quick Reference Commands

### Status Checks

```bash
# All services
systemctl status milkbot-{analytics,dashboard}.service milkbot-trader.timer

# Current trading mode
grep TRADING_MODE /opt/milkbot/.env

# Account balance (live)
cd /opt/milkbot && source venv/bin/activate && python -c "
from src.shared.api.kalshi import KalshiClient
print(f'Balance: \${KalshiClient().get_balance()}')"
```

### Emergency Commands

```bash
# Stop trading
sudo systemctl stop milkbot-trader.timer

# View recent logs
journalctl -u milkbot-trader -n 100

# Cancel all orders
cd /opt/milkbot && source venv/bin/activate && python -c "
from src.trader.oms import OrderManagementSystem
OrderManagementSystem().cancel_all_pending()"

# Check positions
cd /opt/milkbot && source venv/bin/activate && python -c "
from src.trader.oms import OrderManagementSystem
for p in OrderManagementSystem().get_open_positions():
    print(f'{p.ticker}: {p.quantity} @ {p.avg_price}')"
```

### Rollback Commands

```bash
# Restore demo config
cp /opt/milkbot/.env.demo.backup /opt/milkbot/.env
sudo systemctl restart milkbot-{analytics,dashboard}.service
sudo systemctl start milkbot-trader.timer
```
