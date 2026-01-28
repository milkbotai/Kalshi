# Engineering Instructions for Ralph (Milkbot)

## Core Principles
1. **Type safety**: Type hints everywhere; mypy strict.
2. **Testing**: Every function needs tests (happy path + error cases).
3. **Documentation**: Google-style docstrings for all public functions.
4. **Code style**: PEP8; Black + isort; no unused imports; no print().
5. **Git discipline**: Atomic commits (one story per commit) with detailed messages.
6. **Professional UI**: No emojis; minimal scroll; consistent typography.
7. **Security first**: Never log secrets. Never expose trading keys to dashboard.
8. **Determinism**: LLM output is advisory only and cannot affect trade execution.

## Project Guardrails (non-negotiable)
- Public domain is **milkbot.ai** behind Cloudflare.
- **Exact trades are public with a 60-minute delay** enforced server-side.
- Postgres schemas: `ops` (private) and `analytics` (public-safe).
- Dashboard reads only from `analytics` or local analytics API.
- Trader binds to localhost and runs as systemd service in production.

## Story Implementation Workflow (for EACH story in prd.json)
1. **Read requirements**
   - Read story from prd.json
   - Read docs/DEFINITIONS.md for system context
   - Identify dependencies and existing modules

2. **Implement code**
   - Create/modify minimal files required
   - Prefer small, testable functions
   - Use constants instead of magic numbers

3. **Write tests**
   - At least 1 unit test per function
   - Include error cases and edge cases
   - Mock external services (Kalshi, NWS, OpenRouter)

4. **Run quality gates** (must all pass)
   - `pytest -v`
   - `mypy src/ --ignore-missing-imports` (or strict config)
   - `black src/ tests/`
   - `isort src/ tests/`

5. **Commit** (only if ALL gates pass)
   - Commit message format below

6. **Update prd.json + progress.txt**
   - Set story `passes: true`
   - Append a short entry to progress.txt (what changed, files, gotchas)

7. **Move immediately to next story**
   - Do not ask for permission
   - Do not refactor unrelated code

## Code Quality Standards
### Type hints
- All public functions must have explicit input/output types.

### Error handling
- No bare `except:`
- Log with structured logger
- Return safe defaults only in analytics/dashboard layers (not trader)

### Performance rules
- Aggregate in SQL, not Python, for dashboard metrics.
- Cache expensive reads.

## Git Commit Message Format
```
[Story #X.X] Short title
Implementation:
- What changed (files, functions)
- Key decisions
Testing:
- Tests added/updated
- All tests passing
Quality Gates:
✅ pytest
✅ mypy
✅ black
✅ isort
Acceptance Criteria:
✅ Criterion 1
✅ Criterion 2
✅ Criterion 3
Co-Authored-By: Claude <noreply@anthropic.com>
```

## When stuck
If a story takes >30 minutes:
- Split it into smaller stories and update prd.json
- Mark original story as blocked with a note
- Proceed to next unblocked story

NOW: Implement the first incomplete story in prd.json.
