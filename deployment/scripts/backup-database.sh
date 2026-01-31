#!/bin/bash
# Milkbot Database Backup Script
# Usage: ./backup-database.sh [daily|weekly|monthly]
#
# Retention Policy:
#   - Daily backups: 7 days
#   - Weekly backups: 4 weeks
#   - Monthly backups: 12 months

set -euo pipefail

# Configuration
BACKUP_TYPE="${1:-daily}"
BACKUP_DIR="/var/backups/milkbot"
S3_BUCKET="${MILKBOT_BACKUP_BUCKET:-}"
DB_NAME="${POSTGRES_DB:-milkbot}"
DB_USER="${POSTGRES_USER:-milkbot}"
DB_HOST="${POSTGRES_HOST:-localhost}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="/var/log/milkbot/backup.log"

# Retention periods (in days)
DAILY_RETENTION=7
WEEKLY_RETENTION=28
MONTHLY_RETENTION=365

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR: $1"
    exit 1
}

# Create backup directories
mkdir -p "$BACKUP_DIR"/{daily,weekly,monthly}
mkdir -p "$(dirname "$LOG_FILE")"

log "Starting $BACKUP_TYPE backup of database: $DB_NAME"

# Determine backup path
case "$BACKUP_TYPE" in
    daily)
        BACKUP_PATH="$BACKUP_DIR/daily/milkbot_${TIMESTAMP}.sql.gz"
        RETENTION=$DAILY_RETENTION
        ;;
    weekly)
        BACKUP_PATH="$BACKUP_DIR/weekly/milkbot_${TIMESTAMP}.sql.gz"
        RETENTION=$WEEKLY_RETENTION
        ;;
    monthly)
        BACKUP_PATH="$BACKUP_DIR/monthly/milkbot_${TIMESTAMP}.sql.gz"
        RETENTION=$MONTHLY_RETENTION
        ;;
    *)
        error "Invalid backup type: $BACKUP_TYPE. Use: daily, weekly, or monthly"
        ;;
esac

# Perform backup (exclude analytics schema - can be regenerated)
log "Creating backup: $BACKUP_PATH"
pg_dump -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" \
    --exclude-schema=analytics \
    --no-owner \
    --no-acl \
    --verbose \
    2>> "$LOG_FILE" | gzip > "$BACKUP_PATH"

if [[ ! -f "$BACKUP_PATH" ]]; then
    error "Backup file was not created"
fi

BACKUP_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
log "Backup completed: $BACKUP_PATH ($BACKUP_SIZE)"

# Verify backup integrity
log "Verifying backup integrity..."
if ! gunzip -t "$BACKUP_PATH" 2>/dev/null; then
    error "Backup file is corrupted"
fi
log "Backup integrity verified"

# Upload to S3/B2 if configured
if [[ -n "$S3_BUCKET" ]]; then
    log "Uploading to S3: s3://$S3_BUCKET/$BACKUP_TYPE/"
    if command -v aws &> /dev/null; then
        aws s3 cp "$BACKUP_PATH" "s3://$S3_BUCKET/$BACKUP_TYPE/" --only-show-errors
        log "S3 upload completed"
    else
        log "WARNING: AWS CLI not installed, skipping S3 upload"
    fi
fi

# Clean up old backups
log "Cleaning up backups older than $RETENTION days..."
find "$BACKUP_DIR/$BACKUP_TYPE" -name "milkbot_*.sql.gz" -mtime +$RETENTION -delete 2>/dev/null || true

# Count remaining backups
BACKUP_COUNT=$(find "$BACKUP_DIR/$BACKUP_TYPE" -name "milkbot_*.sql.gz" | wc -l)
log "Backup cleanup complete. $BACKUP_COUNT $BACKUP_TYPE backups retained."

log "Backup process completed successfully"
