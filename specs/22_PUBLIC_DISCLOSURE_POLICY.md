# Public Disclosure Policy (milkbot.ai)

## 1. Show exact trades with delay
- Trades displayed exactly (market, side, qty, price)
- **Delay: 60 minutes** enforced at DB view level

## 2. Redactions
- Do not show order_id
- Do not show internal run ids
- Do not show raw request payloads

## 3. Timestamp handling
- Round to nearest minute for public display

---
