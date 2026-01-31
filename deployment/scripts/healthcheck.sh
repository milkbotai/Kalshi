#!/bin/bash
# Milkbot Health Check Script
# Usage: ./healthcheck.sh [--alert]
#
# Returns exit code 0 if all services healthy, 1 otherwise
# Use with external monitoring (UptimeRobot, Healthchecks.io, etc.)

set -uo pipefail

ALERT_MODE="${1:-}"
SLACK_WEBHOOK="${MILKBOT_SLACK_WEBHOOK:-}"
HEALTHCHECKS_URL="${MILKBOT_HEALTHCHECKS_URL:-}"

# Service endpoints
ANALYTICS_URL="http://127.0.0.1:8000/v1/health"
DASHBOARD_URL="http://127.0.0.1:8501/_stcore/health"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_NAME="${POSTGRES_DB:-milkbot}"
DB_USER="${POSTGRES_USER:-milkbot}"

HEALTHY=true
STATUS_REPORT=""

check_service() {
    local name=$1
    local url=$2
    local timeout=${3:-5}

    if curl -sf --max-time "$timeout" "$url" > /dev/null 2>&1; then
        STATUS_REPORT+="$name: OK\n"
        return 0
    else
        STATUS_REPORT+="$name: FAILED\n"
        HEALTHY=false
        return 1
    fi
}

check_systemd_service() {
    local service=$1

    if systemctl is-active --quiet "$service" 2>/dev/null; then
        STATUS_REPORT+="$service: RUNNING\n"
        return 0
    else
        STATUS_REPORT+="$service: NOT RUNNING\n"
        HEALTHY=false
        return 1
    fi
}

check_database() {
    if pg_isready -h "$DB_HOST" -d "$DB_NAME" -U "$DB_USER" -q 2>/dev/null; then
        STATUS_REPORT+="PostgreSQL: OK\n"
        return 0
    else
        STATUS_REPORT+="PostgreSQL: FAILED\n"
        HEALTHY=false
        return 1
    fi
}

check_disk_space() {
    local threshold=90
    local usage=$(df /opt/milkbot 2>/dev/null | tail -1 | awk '{print $5}' | tr -d '%')

    if [[ -n "$usage" && "$usage" -lt "$threshold" ]]; then
        STATUS_REPORT+="Disk Space: ${usage}% used (OK)\n"
        return 0
    else
        STATUS_REPORT+="Disk Space: ${usage:-unknown}% used (WARNING)\n"
        HEALTHY=false
        return 1
    fi
}

check_memory() {
    local threshold=90
    local usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')

    if [[ "$usage" -lt "$threshold" ]]; then
        STATUS_REPORT+="Memory: ${usage}% used (OK)\n"
        return 0
    else
        STATUS_REPORT+="Memory: ${usage}% used (WARNING)\n"
        HEALTHY=false
        return 1
    fi
}

send_alert() {
    local message=$1

    # Slack notification
    if [[ -n "$SLACK_WEBHOOK" ]]; then
        curl -sf -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Milkbot Health Alert\n\`\`\`$message\`\`\`\"}" \
            "$SLACK_WEBHOOK" > /dev/null 2>&1 || true
    fi
}

ping_healthchecks() {
    local status=$1

    if [[ -n "$HEALTHCHECKS_URL" ]]; then
        if [[ "$status" == "ok" ]]; then
            curl -sf --max-time 5 "$HEALTHCHECKS_URL" > /dev/null 2>&1 || true
        else
            curl -sf --max-time 5 "$HEALTHCHECKS_URL/fail" > /dev/null 2>&1 || true
        fi
    fi
}

# Run all checks
echo "=== Milkbot Health Check ==="
echo "Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Service checks
check_database
check_service "Analytics API" "$ANALYTICS_URL"
check_service "Dashboard" "$DASHBOARD_URL" 10
check_systemd_service "milkbot-analytics.service"
check_systemd_service "milkbot-dashboard.service"
check_systemd_service "milkbot-trader.timer"

# System checks
check_disk_space
check_memory

# Output report
echo -e "$STATUS_REPORT"

# Send alerts if unhealthy and alert mode enabled
if [[ "$HEALTHY" == "false" ]]; then
    echo "STATUS: UNHEALTHY"

    if [[ "$ALERT_MODE" == "--alert" ]]; then
        send_alert "$STATUS_REPORT"
    fi

    ping_healthchecks "fail"
    exit 1
else
    echo "STATUS: HEALTHY"
    ping_healthchecks "ok"
    exit 0
fi
