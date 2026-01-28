# Order Management System (OMS) Specification

## 1. Requirements
- Deterministic order creation.
- Idempotent: restarts must not duplicate orders.
- Full reconciliation: open orders/positions must match exchange after restart.

## 2. State machine
NEW → SUBMITTED → RESTING → PARTIAL → FILLED → CLOSED
                      ↘
                       REJECTED/CANCELED

## 3. Idempotency keys
`intent_key = hash(city + market_id + side + strategy + event_date)`

Rules:
- One active intent → one active order.
- Any replacement increments an intent version (intent_key + version).

## 4. Order placement policy
- Always use limit orders.
- Max price is derived from fair value minus minimum edge.

## 5. Cancel/replace policy
- Only replace every REPRICE_INTERVAL seconds.
- Do not chase beyond MAX_CHASE_CENTS.
- Cancel if spread widens beyond threshold or liquidity drops.

## 6. Reconciliation on startup
- Query exchange open orders.
- Query exchange positions.
- Compare to DB; repair local state.
- Emit system event if mismatch.

---
