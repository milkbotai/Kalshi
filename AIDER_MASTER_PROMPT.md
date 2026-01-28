# AIDER AUTONOMOUS SETUP + IMPLEMENTATION PROMPT
# Milkbot Kalshi Weather Trading Platform
# Target: 100% Quality, Zero Human Intervention

You are an autonomous coding agent using Aider. Your mission is to:
1. Set up the complete development environment from scratch
2. Implement all 60 user stories following the Ralph protocol
3. Achieve 100% test coverage and production-ready code quality

## PHASE 0: ENVIRONMENT BOOTSTRAP (Do This First)

### Step 0.1: Create Project Structure
Create complete directory structure with all necessary subdirectories and __init__.py files.

Required directories:
- src/trader, src/analytics, src/dashboard, src/shared (with subdirs: config, models, api, utils)
- tests/unit, tests/integration, tests/fixtures
- infra/migrations, infra/nginx, infra/systemd, infra/backups
- data/cities, data/backtest, data/cache
- logs/, docs/, scripts/

### Step 0.2: Create Configuration Files

Create `.gitignore` with Python, venv, IDE, logs, secrets exclusions
Create `pytest.ini` with 95% coverage requirement and test markers
Create `pyproject.toml` with black, isort, mypy strict settings
Create `.env.example` with all environment variables
Create `.env` by copying .env.example

### Step 0.3: Fetch NWS Grid Coordinates

Create `scripts/fetch_nws_grids.py` that:
- Fetches NWS grid coordinates for 10 cities from weather.gov API
- Creates data/cities/cities.json with full city data including:
  - NYC, CHI, LAX, MIA, AUS, DEN, PHL, BOS, SEA, SFO
  - lat/lon, timezone, NWS office, grid X/Y, settlement station
- Saves complete JSON file for use in implementation

Run the script to populate real weather grid data.

### Step 0.4: Initialize Git Repository

```bash
git init
git add .
git commit -m "chore: initial project structure and configuration"
```

### Step 0.5: Create Progress Tracking

Create `progress.txt` with initial status showing environment setup complete.

## PHASE 1-10: IMPLEMENT ALL 60 STORIES (Ralph Protocol)

### Ralph Iteration Protocol

For each of the 60 stories:

1. READ progress.txt to see what was completed
2. READ prd.json to find next story (check dependencies are met)
3. READ DEFINITIONS.md, PROMPT.md, and relevant spec files
4. IMPLEMENT the story with 100% quality:
   - Full type hints on every function
   - Google-style docstrings with examples
   - Comprehensive tests (95%+ coverage)
   - Meet all acceptance criteria
5. TEST implementation:
   - pytest with coverage check
   - mypy strict mode
   - black and isort formatting
6. COMMIT with semantic message
7. UPDATE progress.txt and mark story complete in prd.json
8. REPEAT for next story

### Quality Standards (100% Compliance Required)

Every single piece of code must have:

✅ Type Safety: mypy --strict with zero errors
✅ Test Coverage: 95%+ (aim for 100%)
✅ Documentation: Every function has detailed docstring
✅ Code Style: black + isort formatted
✅ Error Handling: All exceptions caught and logged
✅ Logging: Structured logging at INFO/ERROR levels
✅ Security: Zero secrets in code (env vars only)
✅ Performance: Optimized queries, caching per specs

### Example Implementation Quality

When implementing a model (e.g., Story 2.3 Position Model):

File: src/trader/models/position.py
- Full type hints on all attributes and methods
- Detailed module and class docstrings
- Property methods with clear logic
- Meaningful __repr__ for debugging

File: tests/unit/test_position_model.py
- Test class with descriptive test methods
- Test all properties and edge cases
- 100% branch coverage
- Clear assertions with messages

### Commit Message Format

```
type(scope): subject

Story: X.Y
Acceptance: [criteria met]
Tests: [count] passing, coverage [%]
```

Types: feat, fix, docs, test, refactor, chore

### Dependency Management

Stories have dependencies in prd.json. Example:
- Story 2.3 depends on [1.5, 2.1]
- Must complete 1.5 and 2.1 before starting 2.3

Always check dependencies array before implementing.

### Progress Tracking

After each story, append to progress.txt:

```
## Story X.Y Complete
Date: [timestamp]
Story: X.Y - [Name]
Files: [list of files created/modified]
Tests: [count] passing
Coverage: [%]
Commit: [hash]

---
```

### Critical Context Files

Read these BEFORE implementing any story:

1. DEFINITIONS.md - System architecture, business rules
2. PROMPT.md - Engineering standards
3. prd.json - All 60 stories with dependencies
4. specs/04_DATA_MODEL.md - Database schema
5. specs/15_STRATEGY_SPEC.md - Trading strategies
6. specs/16_RISK_POLICY.md - Risk management

### Non-Negotiable Constraints

Security:
- Public dashboard NEVER has API keys
- All secrets in environment variables only
- 5-minute trade delay before public disclosure

Architecture:
- 3 services: trader, analytics, dashboard
- PostgreSQL for all persistence
- Single Ubuntu VPS deployment

Trading Rules:
- LLM NEVER makes trading decisions (weather context only)
- All strategies are deterministic and auditable
- Risk limits: $1000 max position, $100 max daily loss
- 10-day demo validation required before live mode

Quality Gates (must pass before story is complete):
- pytest -v --cov=src --cov-fail-under=95
- mypy src/ --strict (zero errors)
- black --check src/ tests/ (zero changes needed)
- isort --check-only src/ tests/ (zero changes needed)

### When All 60 Stories Are Complete

Append to progress.txt:

```
## PROJECT COMPLETE
Date: [timestamp]
Total Stories: 60/60
Total Tests: [count]
Coverage: [%]
Status: ✅ ALL QUALITY GATES PASSING

RALPH_COMPLETE
```

---

## EXECUTION INSTRUCTIONS

Start immediately with Step 0.1 (Create Project Structure).

Do NOT wait for confirmation.
Do NOT ask questions.
Proceed with full autonomy.

Work sequentially:
1. Complete Phase 0 (Steps 0.1-0.5)
2. Implement Stories 1.1 through 10.3 in dependency order
3. Maintain 100% quality at all times
4. Stop only when RALPH_COMPLETE is written

Quality Target: 100%
Autonomy: Full
Human Intervention: Zero

BEGIN EXECUTION NOW.
