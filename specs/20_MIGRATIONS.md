# Database Migrations

## 1. Tooling
Use Alembic or a simple SQL migrations folder.

## 2. Rules
- Every schema change gets a migration.
- Migrations are run in CI for integration tests.
- Production migrations are run before services restart.

## 3. Rollback
- Keep downgrade scripts where feasible.
- For destructive changes, stage a copy migration.

---
