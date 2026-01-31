#!/bin/bash
# Milkbot Database Restore Script
# Usage: ./restore-database.sh <backup_file.sql.gz>
#
# WARNING: This will DROP and RECREATE the database!
# Always verify you have a recent backup before restoring.

set -euo pipefail

# Configuration
BACKUP_FILE="${1:-}"
DB_NAME="${POSTGRES_DB:-milkbot}"
DB_USER="${POSTGRES_USER:-milkbot}"
DB_HOST="${POSTGRES_HOST:-localhost}"
LOG_FILE="/var/log/milkbot/restore.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR: $1"
    exit 1
}

# Validate input
if [[ -z "$BACKUP_FILE" ]]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Available backups:"
    find /var/backups/milkbot -name "milkbot_*.sql.gz" -printf "  %p (%s bytes, %Tc)\n" 2>/dev/null | sort -r | head -20
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    error "Backup file not found: $BACKUP_FILE"
fi

mkdir -p "$(dirname "$LOG_FILE")"

log "=== DATABASE RESTORE STARTED ==="
log "Backup file: $BACKUP_FILE"
log "Target database: $DB_NAME"
log "Host: $DB_HOST"

# Verify backup integrity
log "Verifying backup file integrity..."
if ! gunzip -t "$BACKUP_FILE" 2>/dev/null; then
    error "Backup file is corrupted or invalid"
fi
log "Backup file integrity verified"

# Confirm with user
echo ""
echo "WARNING: This will DROP and RECREATE the database '$DB_NAME'!"
echo "All existing data will be LOST!"
echo ""
read -p "Type 'RESTORE' to confirm: " CONFIRM

if [[ "$CONFIRM" != "RESTORE" ]]; then
    log "Restore cancelled by user"
    exit 0
fi

# Stop services
log "Stopping Milkbot services..."
systemctl stop milkbot-trader.timer 2>/dev/null || true
systemctl stop milkbot-trader.service 2>/dev/null || true
systemctl stop milkbot-analytics.service 2>/dev/null || true
systemctl stop milkbot-dashboard.service 2>/dev/null || true
sleep 5

# Drop existing database and create fresh
log "Dropping existing database..."
psql -h "$DB_HOST" -U postgres -c "DROP DATABASE IF EXISTS $DB_NAME;" 2>> "$LOG_FILE"

log "Creating fresh database..."
psql -h "$DB_HOST" -U postgres -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;" 2>> "$LOG_FILE"

# Restore from backup
log "Restoring from backup (this may take a while)..."
gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" 2>> "$LOG_FILE"

if [[ $? -ne 0 ]]; then
    error "Database restore failed"
fi

log "Database restore completed"

# Recreate analytics schema (excluded from backup)
log "Recreating analytics schema..."
psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c "CREATE SCHEMA IF NOT EXISTS analytics;" 2>> "$LOG_FILE"

# Run analytics rollups to regenerate data
log "Regenerating analytics rollups..."
cd /opt/milkbot
/opt/milkbot/venv/bin/python -c "from src.analytics.rollups import run_daily_rollups; run_daily_rollups()" 2>> "$LOG_FILE" || log "WARNING: Rollups regeneration failed (may need manual intervention)"

# Restart services
log "Restarting Milkbot services..."
systemctl start milkbot-analytics.service 2>/dev/null || true
systemctl start milkbot-dashboard.service 2>/dev/null || true
systemctl start milkbot-trader.timer 2>/dev/null || true

# Verify services
sleep 5
log "Verifying service status..."
systemctl is-active milkbot-analytics.service && log "Analytics service: RUNNING" || log "WARNING: Analytics service not running"
systemctl is-active milkbot-dashboard.service && log "Dashboard service: RUNNING" || log "WARNING: Dashboard service not running"

log "=== DATABASE RESTORE COMPLETED ==="
log "Please verify the application is functioning correctly"
