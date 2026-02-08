# Deployment Runbook

**Document Version:** 1.0
**Last Updated:** 2026-01-30

This runbook covers initial VPS setup, code deployment, database migrations, service restarts, and rollback procedures for the Milkbot trading platform.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Initial VPS Setup](#2-initial-vps-setup)
3. [Code Deployment](#3-code-deployment)
4. [Database Setup & Migrations](#4-database-setup--migrations)
5. [Service Configuration](#5-service-configuration)
6. [Starting Services](#6-starting-services)
7. [Verification](#7-verification)
8. [Rollback Procedures](#8-rollback-procedures)
9. [Updating Deployments](#9-updating-deployments)

---

## 1. Prerequisites

### 1.1 VPS Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 4 cores | 6 cores |
| RAM | 8 GB | 12 GB |
| Disk | 100 GB SSD | 200 GB SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 24.04 LTS |

### 1.2 Domain & SSL

- Domain: `milkbot.ai` pointed to VPS IP
- SSL: Cloudflare Origin Certificate (or Let's Encrypt)
- Cloudflare: Proxy enabled, SSL mode "Full (strict)"

### 1.3 Required Credentials

Before starting, ensure you have:

- [ ] Kalshi demo API credentials (email/password)
- [ ] PostgreSQL password (generate secure password)
- [ ] OpenRouter API key (optional, for LLM features)
- [ ] Cloudflare Origin Certificate and key
- [ ] SSH key for VPS access

---

## 2. Initial VPS Setup

### 2.1 System Packages

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    postgresql-15 \
    postgresql-contrib \
    nginx \
    git \
    curl \
    jq \
    logrotate \
    htop \
    unzip

# Verify Python version
python3.12 --version
```

### 2.2 Create Service User

```bash
# Create milkbot user (no login shell for security)
sudo useradd --system --create-home --home-dir /opt/milkbot --shell /usr/sbin/nologin milkbot

# Create required directories
sudo mkdir -p /opt/milkbot/{data,logs}
sudo mkdir -p /var/log/milkbot
sudo mkdir -p /var/backups/milkbot/{daily,weekly,monthly}

# Set ownership
sudo chown -R milkbot:milkbot /opt/milkbot
sudo chown -R milkbot:milkbot /var/log/milkbot
sudo chown -R milkbot:milkbot /var/backups/milkbot
```

### 2.3 Configure PostgreSQL

```bash
# Start PostgreSQL
sudo systemctl enable postgresql
sudo systemctl start postgresql

# Create database and user
sudo -u postgres psql <<EOF
CREATE USER milkbot WITH PASSWORD 'YOUR_SECURE_PASSWORD';
CREATE DATABASE milkbot OWNER milkbot;
GRANT ALL PRIVILEGES ON DATABASE milkbot TO milkbot;
\c milkbot
CREATE SCHEMA IF NOT EXISTS ops;
CREATE SCHEMA IF NOT EXISTS analytics;
GRANT ALL ON SCHEMA ops TO milkbot;
GRANT ALL ON SCHEMA analytics TO milkbot;
EOF

# Verify connection
psql -U milkbot -d milkbot -h localhost -c "SELECT version();"
```

### 2.4 Configure Firewall

```bash
# Allow SSH, HTTP, HTTPS only
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable

# Verify
sudo ufw status
```

---

## 3. Code Deployment

### 3.1 Clone Repository

```bash
# Switch to milkbot user context
sudo -u milkbot bash

cd /opt/milkbot

# Clone repository (or copy from secure location)
git clone https://github.com/milkbotai/Kalshi.git .

# Or if deploying from tarball
# tar -xzf milkbot-v1.0.0.tar.gz -C /opt/milkbot
```

### 3.2 Create Virtual Environment

```bash
cd /opt/milkbot

# Create venv with Python 3.12
python3.12 -m venv venv

# Activate and upgrade pip
source venv/bin/activate
pip install --upgrade pip

# Install dependencies
pip install -e ".[dev]"

# Verify installation
python -c "from src.trader.trading_loop import TradingLoop; print('OK')"
```

### 3.3 Configure Environment

```bash
# Copy environment template
cp /opt/milkbot/.env.example /opt/milkbot/.env

# Edit with secure values
nano /opt/milkbot/.env
```

**Required `.env` settings:**

```bash
# Trading mode (start with demo!)
TRADING_MODE=demo

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=milkbot
POSTGRES_USER=milkbot
POSTGRES_PASSWORD=YOUR_SECURE_PASSWORD

# Kalshi API (Demo)
KALSHI_API_BASE=https://demo-api.kalshi.co/trade-api/v2
KALSHI_EMAIL=your_email@example.com
KALSHI_PASSWORD=your_kalshi_password

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

**Secure the file:**

```bash
chmod 600 /opt/milkbot/.env
chown milkbot:milkbot /opt/milkbot/.env
```

---

## 4. Database Setup & Migrations

### 4.1 Run Schema Migrations

```bash
cd /opt/milkbot
source venv/bin/activate

# Run migrations in order
psql -U milkbot -d milkbot -f src/shared/db/migrations/001_create_schemas.sql
psql -U milkbot -d milkbot -f src/shared/db/migrations/002_create_public_trades_view.sql

# Initialize tables via SQLAlchemy
python -c "
from src.shared.db.connection import get_engine
from src.shared.db.models import Base
engine = get_engine()
Base.metadata.create_all(engine)
print('Tables created successfully')
"
```

### 4.2 Verify Database Setup

```bash
# Check schemas exist
psql -U milkbot -d milkbot -c "\dn"

# Check tables created
psql -U milkbot -d milkbot -c "\dt ops.*"

# Verify analytics view
psql -U milkbot -d milkbot -c "\dv analytics.*"
```

### 4.3 Database Migration Checklist

For future migrations:

1. [ ] Backup database before migration
2. [ ] Test migration on staging first
3. [ ] Run migration during low-activity window
4. [ ] Verify application compatibility
5. [ ] Monitor for errors after migration

---

## 5. Service Configuration

### 5.1 Install Systemd Services

```bash
# Copy service files
sudo cp /opt/milkbot/deployment/systemd/*.service /etc/systemd/system/
sudo cp /opt/milkbot/deployment/systemd/*.timer /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services (but don't start yet)
sudo systemctl enable milkbot-analytics.service
sudo systemctl enable milkbot-dashboard.service
sudo systemctl enable milkbot-trader.timer
sudo systemctl enable milkbot-rollups.timer
```

### 5.2 Configure NGINX

```bash
# Copy NGINX configuration
sudo cp /opt/milkbot/deployment/nginx/milkbot.conf /etc/nginx/sites-available/

# Create symlink
sudo ln -sf /etc/nginx/sites-available/milkbot.conf /etc/nginx/sites-enabled/

# Remove default site
sudo rm -f /etc/nginx/sites-enabled/default

# Install SSL certificate (from Cloudflare)
sudo mkdir -p /etc/ssl/certs /etc/ssl/private
sudo nano /etc/ssl/certs/milkbot.ai.pem    # Paste certificate
sudo nano /etc/ssl/private/milkbot.ai.key  # Paste private key
sudo chmod 600 /etc/ssl/private/milkbot.ai.key

# Test configuration
sudo nginx -t

# Reload NGINX
sudo systemctl reload nginx
```

### 5.3 Configure Log Rotation

```bash
# Copy logrotate configuration
sudo cp /opt/milkbot/deployment/logrotate/milkbot /etc/logrotate.d/

# Test configuration
sudo logrotate -d /etc/logrotate.d/milkbot
```

### 5.4 Configure Backup Cron

```bash
# Add backup jobs to crontab
sudo crontab -e
```

Add the following lines:

```cron
# Milkbot database backups
0 2 * * * /opt/milkbot/deployment/scripts/backup-database.sh daily >> /var/log/milkbot/backup.log 2>&1
0 3 * * 0 /opt/milkbot/deployment/scripts/backup-database.sh weekly >> /var/log/milkbot/backup.log 2>&1
0 4 1 * * /opt/milkbot/deployment/scripts/backup-database.sh monthly >> /var/log/milkbot/backup.log 2>&1

# Health check (every 5 minutes)
*/5 * * * * /opt/milkbot/deployment/scripts/healthcheck.sh --alert >> /var/log/milkbot/healthcheck.log 2>&1
```

---

## 6. Starting Services

### 6.1 Startup Order

Services must be started in this order:

1. PostgreSQL (should already be running)
2. Analytics API
3. Dashboard
4. Trader (via timer)

```bash
# 1. Verify PostgreSQL
sudo systemctl status postgresql

# 2. Start Analytics API
sudo systemctl start milkbot-analytics.service
sleep 5
curl -s http://127.0.0.1:8000/v1/health | jq .

# 3. Start Dashboard
sudo systemctl start milkbot-dashboard.service
sleep 10
curl -s http://127.0.0.1:8501/_stcore/health

# 4. Start Trader Timer
sudo systemctl start milkbot-trader.timer

# 5. Start Rollups Timer
sudo systemctl start milkbot-rollups.timer

# Verify all services
systemctl status milkbot-*.service milkbot-*.timer
```

### 6.2 Verify External Access

```bash
# Test NGINX proxy
curl -I https://milkbot.ai/health

# Test dashboard access
curl -I https://milkbot.ai/

# Check NGINX logs for errors
tail -f /var/log/nginx/milkbot-error.log
```

---

## 7. Verification

### 7.1 Post-Deployment Checklist

Run through this checklist after every deployment:

**Services:**
- [ ] `systemctl is-active milkbot-analytics.service` returns "active"
- [ ] `systemctl is-active milkbot-dashboard.service` returns "active"
- [ ] `systemctl is-active milkbot-trader.timer` returns "active"

**Endpoints:**
- [ ] `curl http://127.0.0.1:8000/v1/health` returns 200
- [ ] `curl http://127.0.0.1:8501/_stcore/health` returns 200
- [ ] `curl https://milkbot.ai/` loads dashboard

**Database:**
- [ ] `pg_isready -h localhost -d milkbot -U milkbot` returns "accepting connections"
- [ ] Can query tables: `psql -U milkbot -d milkbot -c "SELECT 1"`

**Logs:**
- [ ] No errors in `journalctl -u milkbot-analytics -n 50`
- [ ] No errors in `journalctl -u milkbot-dashboard -n 50`
- [ ] No errors in `journalctl -u milkbot-trader -n 50`

### 7.2 Full Health Check

```bash
# Run comprehensive health check
/opt/milkbot/deployment/scripts/healthcheck.sh
```

---

## 8. Rollback Procedures

### 8.1 Code Rollback

If a deployment causes issues, rollback to the previous version:

```bash
# 1. Stop all services
sudo systemctl stop milkbot-trader.timer
sudo systemctl stop milkbot-dashboard.service
sudo systemctl stop milkbot-analytics.service

# 2. Rollback code
cd /opt/milkbot

# If using git
git log --oneline -5  # Find previous commit
git checkout <previous-commit-hash>

# Or restore from backup
# tar -xzf /var/backups/milkbot/code/milkbot-previous.tar.gz -C /opt/milkbot

# 3. Reinstall dependencies (if needed)
source venv/bin/activate
pip install -e ".[dev]"

# 4. Restart services
sudo systemctl start milkbot-analytics.service
sudo systemctl start milkbot-dashboard.service
sudo systemctl start milkbot-trader.timer

# 5. Verify
/opt/milkbot/deployment/scripts/healthcheck.sh
```

### 8.2 Database Rollback

**WARNING:** Database rollback is destructive. Only use if necessary.

```bash
# 1. Stop all services
sudo systemctl stop milkbot-trader.timer
sudo systemctl stop milkbot-dashboard.service
sudo systemctl stop milkbot-analytics.service

# 2. List available backups
ls -la /var/backups/milkbot/daily/

# 3. Restore from backup
/opt/milkbot/deployment/scripts/restore-database.sh /var/backups/milkbot/daily/milkbot_YYYYMMDD_HHMMSS.sql.gz

# 4. Restart services
sudo systemctl start milkbot-analytics.service
sudo systemctl start milkbot-dashboard.service
sudo systemctl start milkbot-trader.timer
```

### 8.3 Emergency Rollback (Complete)

For critical failures requiring full rollback:

```bash
#!/bin/bash
# Emergency rollback script

echo "=== EMERGENCY ROLLBACK ==="
echo "This will stop all services and restore from backup"
read -p "Continue? (yes/no): " confirm
[[ "$confirm" != "yes" ]] && exit 1

# Stop everything
sudo systemctl stop milkbot-trader.timer
sudo systemctl stop milkbot-trader.service
sudo systemctl stop milkbot-dashboard.service
sudo systemctl stop milkbot-analytics.service

# Rollback code
cd /opt/milkbot
git fetch origin
git reset --hard origin/main~1  # Go back one commit

# Restore database
LATEST_BACKUP=$(ls -t /var/backups/milkbot/daily/*.sql.gz | head -1)
/opt/milkbot/deployment/scripts/restore-database.sh "$LATEST_BACKUP"

# Restart
sudo systemctl start milkbot-analytics.service
sudo systemctl start milkbot-dashboard.service
sudo systemctl start milkbot-trader.timer

echo "=== ROLLBACK COMPLETE ==="
/opt/milkbot/deployment/scripts/healthcheck.sh
```

---

## 9. Updating Deployments

### 9.1 Standard Update Procedure

```bash
# 1. Create backup
/opt/milkbot/deployment/scripts/backup-database.sh daily

# 2. Pull latest code
cd /opt/milkbot
sudo -u milkbot git pull origin main

# 3. Update dependencies
source venv/bin/activate
pip install -e ".[dev]"

# 4. Run any new migrations
# Check for new migration files and run them
ls src/shared/db/migrations/

# 5. Restart services (rolling restart)
sudo systemctl restart milkbot-analytics.service
sleep 5
sudo systemctl restart milkbot-dashboard.service
sleep 5
sudo systemctl restart milkbot-trader.service

# 6. Verify
/opt/milkbot/deployment/scripts/healthcheck.sh
```

### 9.2 Zero-Downtime Update (Advanced)

For updates without dashboard downtime:

```bash
# Trader can be stopped without affecting dashboard
sudo systemctl stop milkbot-trader.timer

# Update code
cd /opt/milkbot
sudo -u milkbot git pull origin main
source venv/bin/activate
pip install -e ".[dev]"

# Restart analytics first (dashboard depends on it)
sudo systemctl restart milkbot-analytics.service
sleep 5

# Verify analytics
curl -s http://127.0.0.1:8000/v1/health

# Restart dashboard
sudo systemctl restart milkbot-dashboard.service
sleep 10

# Verify dashboard
curl -s http://127.0.0.1:8501/_stcore/health

# Restart trader
sudo systemctl start milkbot-trader.timer
```

---

## Appendix A: Troubleshooting

### Service Won't Start

```bash
# Check logs
journalctl -u milkbot-analytics.service -n 100

# Check Python imports
cd /opt/milkbot
source venv/bin/activate
python -c "from src.trader.trading_loop import TradingLoop; print('OK')"

# Verify environment file
cat /opt/milkbot/.env | grep -v PASSWORD
```

### Database Connection Failed

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check connection
pg_isready -h localhost -d milkbot -U milkbot

# Check pg_hba.conf allows local connections
sudo cat /etc/postgresql/*/main/pg_hba.conf | grep milkbot
```

### NGINX 502 Bad Gateway

```bash
# Check backend services are running
curl http://127.0.0.1:8000/v1/health
curl http://127.0.0.1:8501/_stcore/health

# Check NGINX logs
tail -f /var/log/nginx/milkbot-error.log

# Verify NGINX config
sudo nginx -t
```

---

## Appendix B: File Locations

| File | Location |
|------|----------|
| Application | `/opt/milkbot/` |
| Virtual env | `/opt/milkbot/venv/` |
| Environment | `/opt/milkbot/.env` |
| Application logs | `/var/log/milkbot/` |
| NGINX logs | `/var/log/nginx/milkbot-*.log` |
| Database backups | `/var/backups/milkbot/` |
| Systemd services | `/etc/systemd/system/milkbot-*` |
| NGINX config | `/etc/nginx/sites-available/milkbot.conf` |
| Logrotate config | `/etc/logrotate.d/milkbot` |
