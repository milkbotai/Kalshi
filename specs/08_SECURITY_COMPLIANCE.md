# Security & Compliance

## 1. Key principles
- Trading credentials never exposed to public service.
- Least-privilege users.
- Defense-in-depth: firewall + service isolation + secret management.

## 2. Secrets management
- Store secrets in environment variables or encrypted secret store.
- Do not log secrets.
- Rotate keys quarterly or after incidents.

## 3. Network segmentation (single VPS)
- NGINX exposes 80/443 publicly.
- Trader and analytics bind only to localhost.
- Postgres binds only to localhost.

## 4. Public trade display safety
- 60-minute delay enforced at DB view level.
- Strip internal identifiers.

---
