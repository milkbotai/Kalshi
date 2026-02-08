#!/usr/bin/env bash

set -euo pipefail

VPS_IP="${1:-}"
SSH_USER="${2:-$(whoami)}"
# Auto-detect project directory from script location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_DIR="/opt/milkbot"

if [[ -z "$VPS_IP" ]]; then
    echo "Usage: $0 <VPS_IP> [SSH_USER]"
    echo "Example: $0 192.168.1.100 ubuntu"
    exit 1
fi

echo "Starting Milkbot deployment to $SSH_USER@$VPS_IP"

# 1. Create deployment package
echo "Preparing deployment package..."
cd "$PROJECT_DIR"
TEMP_PACKAGE=$(mktemp -d)/milkbot-deploy.tar.gz

tar --exclude='.git' \
    --exclude='.env' \
    --exclude='*.pem' \
    --exclude='*.key' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.pytest_cache' \
    --exclude='.mypy_cache' \
    --exclude='.coverage' \
    --exclude='htmlcov' \
    --exclude='*.log' \
    --exclude='.venv' \
    -czf "$TEMP_PACKAGE" .

# 2. Transfer to VPS
echo "Transferring files..."
scp "$TEMP_PACKAGE" "$SSH_USER@$VPS_IP:/tmp/"

# 3. Deploy on VPS
echo "Deploying on VPS..."
ssh "$SSH_USER@$VPS_IP" "
    set -e
    echo 'Setting up deployment...'
    sudo mkdir -p $DEPLOY_DIR
    sudo tar -xzf /tmp/$(basename $TEMP_PACKAGE) -C $DEPLOY_DIR --strip-components=1
    sudo chown -R milkbot:milkbot $DEPLOY_DIR
    sudo rm /tmp/$(basename $TEMP_PACKAGE)

    echo 'Setting up Python environment...'
    cd $DEPLOY_DIR
    sudo -u milkbot python3.11 -m venv venv
    sudo -u milkbot venv/bin/pip install --upgrade pip
    sudo -u milkbot venv/bin/pip install -r requirements.txt

    echo 'Running database migrations...'
    sudo -u milkbot PYTHONPATH=$DEPLOY_DIR venv/bin/python -m src.shared.db.migrate || {
        echo 'WARNING: Database migrations failed. Check DB connectivity and .env config.'
        echo 'You can re-run manually: sudo -u milkbot PYTHONPATH=$DEPLOY_DIR venv/bin/python -m src.shared.db.migrate'
    }

    echo 'Setting up systemd services...'
    sudo cp deployment/systemd/*.service /etc/systemd/system/
    sudo cp deployment/systemd/*.timer /etc/systemd/system/
    sudo systemctl daemon-reload

    echo 'Setting up credentials...'
    sudo cp $DEPLOY_DIR/.env.example $DEPLOY_DIR/.env
    sudo chmod 600 $DEPLOY_DIR/.env
    sudo chown milkbot:milkbot $DEPLOY_DIR/.env

    # Create placeholder for private key
    if [ ! -f $DEPLOY_DIR/kalshi_private_key.pem ]; then
        sudo touch $DEPLOY_DIR/kalshi_private_key.pem
        sudo chmod 600 $DEPLOY_DIR/kalshi_private_key.pem
        sudo chown milkbot:milkbot $DEPLOY_DIR/kalshi_private_key.pem
    fi

    echo ''
    echo '========================================='
    echo ' Deployment complete!'
    echo '========================================='
    echo ''
    echo 'Run these commands to finish setup:'
    echo ''
    echo '1. Set your Kalshi API key:'
    echo '   sudo sed -i \"s/^KALSHI_API_KEY_ID=.*/KALSHI_API_KEY_ID=YOUR_KEY_ID_HERE/\" /opt/milkbot/.env'
    echo '   sudo sed -i \"s|^KALSHI_PRIVATE_KEY_PATH=.*|KALSHI_PRIVATE_KEY_PATH=/opt/milkbot/kalshi_private_key.pem|\" /opt/milkbot/.env'
    echo ''
    echo '2. Paste your private key:'
    echo '   sudo nano /opt/milkbot/kalshi_private_key.pem'
    echo ''
    echo '3. Start services:'
    echo '   sudo systemctl enable milkbot-trader.timer milkbot-dashboard milkbot-analytics'
    echo '   sudo systemctl start milkbot-trader.timer milkbot-dashboard milkbot-analytics'
"

echo "Deployment finished!"
echo "Files transferred to $DEPLOY_DIR on your VPS"
echo ""
echo "SSH in and finish setup:"
echo "   ssh $SSH_USER@$VPS_IP"
echo ""
echo "Then paste your API key and private key (see instructions above)"
