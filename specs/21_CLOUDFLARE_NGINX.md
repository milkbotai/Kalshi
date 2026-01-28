# Cloudflare + NGINX Checklist

## 1. Cloudflare
- DNS A record: milkbot.ai → VPS IP (proxied)
- SSL/TLS: Full (strict)
- Origin cert installed on VPS

## 2. NGINX
- Redirect 80 → 443
- Proxy to Streamlit on 127.0.0.1:8501
- Websocket headers set:
  - Upgrade
  - Connection: upgrade

## 3. Timeouts
- proxy_read_timeout >= 3600

## 4. Caching
- No caching for dashboard pages/websocket.

---
