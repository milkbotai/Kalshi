# Milkbot Weather Trading Platform (Kalshi) — Enterprise Documentation Pack

**Version:** 1.0  
**Date:** 2026-01-23  
**Audience:** Engineering (Backend, Data, DevOps/SRE, Frontend)  

## What this pack contains
This repository-style document set is the **single source of truth** to build and operate:

1) **Trading Engine (private)** — places trades on Kalshi (demo → live) using weather + market data with strict risk controls.
2) **Analytics/API (internal)** — produces sanitized, delayed metrics for public consumption.
3) **Public Dashboard (milkbot.ai)** — beautiful UI that displays metrics and **exact trades with a 60-minute delay**.

## Quick navigation
- [01_PRD.md](01_PRD.md) — product requirements, scope, success metrics
- [02_ARCHITECTURE.md](02_ARCHITECTURE.md) — system decomposition, data flow
- [03_TECH_SPEC.md](03_TECH_SPEC.md) — detailed module specs and interfaces
- [04_DATA_MODEL.md](04_DATA_MODEL.md) — Postgres schemas, tables, and views
- [05_API_CONTRACTS.md](05_API_CONTRACTS.md) — internal API endpoints + payloads
- [06_UI_SPEC.md](06_UI_SPEC.md) — Streamlit UI layout, components, styling
- [07_DEPLOYMENT_RUNBOOK.md](07_DEPLOYMENT_RUNBOOK.md) — Cloudflare/NGINX/systemd, rollout steps
- [08_SECURITY_COMPLIANCE.md](08_SECURITY_COMPLIANCE.md) — secrets, isolation, hardening
- [09_TESTING_QA.md](09_TESTING_QA.md) — unit/integration/perf testing strategy
- [10_OPERATIONS_SRE.md](10_OPERATIONS_SRE.md) — monitoring, alerting, incident playbooks
- [11_DEMO_TO_LIVE_PLAYBOOK.md](11_DEMO_TO_LIVE_PLAYBOOK.md) — 10-day demo plan, go/no-go gates
- [12_LLM_OPENROUTER_POLICY.md](12_LLM_OPENROUTER_POLICY.md) — allowed uses, routing, budgets
- [13_CITY_CONFIG.md](13_CITY_CONFIG.md) — 10-city list, station/grid mapping placeholders
- [14_BACKTEST_DATA_PLAN.md](14_BACKTEST_DATA_PLAN.md) — data capture plan + evaluation framework

## Non-goals / disclaimers
- No guarantees of profitability. The system is built for **robustness, auditability, and controlled risk**.
- Public dashboard shows **delayed trades (60 minutes)** to reduce strategy leakage.

---
