# Deployment Runbook (Ubuntu VPS + Cloudflare + NGINX + systemd)

## 1. Prereqs
- Ubuntu Server LTS installed
- DNS: `milkbot.ai` proxied via Cloudflare
- Firewall: allow 80/443, restricted SSH

## 2. Cloudflare
1) SSL/TLS mode: **Full (strict)**
2) Create Cloudflare Origin Certificate
3) Install cert+key on VPS

## 3. Install core packages
```bash
sudo apt update && sudo apt -y upgrade
sudo apt -y install nginx postgresql postgresql-contrib python3.11 python3.11-venv git
```

## 4. Postgres setup
- Create db `milkbot`
- Create schemas `ops` and `analytics`
- Apply migrations from `infra/migrations/`

## 5. App deployment
### Option A (recommended): systemd services
- `milkbot-trader.service`
- `milkbot-analytics.service`
- `milkbot-dashboard.service`

Each runs in its own venv under `/opt/milkbot/`.

## 6. NGINX reverse proxy
- Configure server blocks for `milkbot.ai`
- Proxy to Streamlit on localhost:8501
- Ensure websocket headers are present

## 7. Observability
- Logs to `/var/log/milkbot/` (JSON)
- Alerts to Slack/email

## 8. Release process
- Deploy in DEMO mode
- Run smoke tests
- Keep 10-day demo validation

---

## Appendix A — systemd unit templates
### /etc/systemd/system/milkbot-trader.service
```ini
[Unit]
Description=Milkbot Trader
After=network.target postgresql.service

[Service]
User=milkbot
WorkingDirectory=/opt/milkbot
Environment=ENV=prod
ExecStart=/opt/milkbot/venv/bin/python -m src.trader.main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### /etc/systemd/system/milkbot-dashboard.service
```ini
[Unit]
Description=Milkbot Public Dashboard
After=network.target

[Service]
User=milkbot
WorkingDirectory=/opt/milkbot
ExecStart=/opt/milkbot/venv/bin/streamlit run src/dashboard/app.py --server.address 127.0.0.1 --server.port 8501
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---
