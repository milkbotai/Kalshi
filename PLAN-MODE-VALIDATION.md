# Pre-Flight Validation Checklist (Milkbot)
Run these in Claude Code **Plan Mode** before starting Ralph.

## ✅ Validation 1: Documentation Complete (20 min)
Prompt:
- Review docs/DEFINITIONS.md
- Confirm the following are fully specified:
  1) 3-service architecture (trader/analytics/dashboard)
  2) Postgres schemas `ops` and `analytics`
  3) Public trade delay policy (60 minutes) and redactions
  4) 10 cities listed with required config fields (tz, cluster, NWS mapping placeholders)
  5) Risk policy defaults for $5k demo
  6) OMS idempotency + reconciliation requirements
  7) OpenRouter policy (advisory only)
List any gaps.

## ✅ Validation 2: PRD Structure (30 min)
Prompt:
- Review prd.json
- Requirements:
  1) 35–60 stories total
  2) Each story 1–2 hours max
  3) 3–5 acceptance criteria per story (binary/verifiable)
  4) Dependency order: foundation → models → DB → trader → analytics → dashboard → deployment
  5) No circular dependencies
  6) Story 1.1 has **zero** external dependencies
List any issues and propose fixes.

## ✅ Validation 3: Test Infrastructure (15 min)
Prompt:
- Verify pytest.ini exists with markers: unit, integration
- tests/conftest.py has fixtures for:
  - sample market snapshot
  - sample weather snapshot
  - sample order/fill
- Ensure `pytest -v` runs and at least 3 tests pass

## ✅ Validation 4: Environment Setup (15 min)
Prompt:
- requirements.txt contains:
  - requests, httpx (optional), pydantic, psycopg (or SQLAlchemy), streamlit, plotly
  - pytest, pytest-cov, mypy, black, isort
- .gitignore excludes venv/, __pycache__/, .env, logs/
- venv activates and imports streamlit

## ✅ Validation 5: First Story Safety (20 min)
Prompt:
- Validate Story 1.1:
  - simple constants/config/fixtures
  - no DB, no API calls
  - complete in <1 hour

## ✅ Validation 6: Data Flow & Delay Enforcement (15 min)
Prompt:
- Trace data flow:
  - trader → ops tables
  - rollups → analytics tables/views
  - dashboard → analytics only
- Confirm delay enforcement is server-side:
  - analytics.v_public_trades filters `now() - 60 minutes`

## ✅ Validation 7: Cloudflare/NGINX readiness (10 min)
Prompt:
- Confirm deployment plan:
  - NGINX reverse proxy to Streamlit with websocket headers
  - Only ports 80/443 public
  - Postgres bound to localhost

## Pre-flight CLI sanity script
```bash
cd /home/milk/repos/Kalshi
python --version
pytest -q
mypy src/ --ignore-missing-imports
black --check src/ tests/
isort --check-only src/ tests/
```

If all validations pass, proceed to PRD generation and run Ralph.
