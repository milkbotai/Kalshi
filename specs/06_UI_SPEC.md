# UI Specification (Public Dashboard — milkbot.ai)

## 1. Purpose
Public, professional dashboard for monitoring Milkbot’s performance across 10 cities.
Shows exact trades **delayed 60 minutes**.

## 2. Layout (zero-scroll desktop)
### 2.1 Hero section (top ~20%)
4 KPI cards:
- Total P&L
- Win Rate
- Trades Today
- Active Positions

Typography:
- 48px primary numbers
- 18px labels

### 2.2 City grid (middle ~60%)
- Desktop: 2 rows × 5 columns
- Tablet: 2 × 3
- Mobile: 1 column

Each card:
- City name 24px
- Temp 32px
- P&L 28px
- Status indicator (CSS dot)

### 2.3 Performance chart (bottom ~20%)
- Plotly area chart
- height 300px
- last 30 days

## 3. Color palette (dark)
- Background: #0E1117
- Cards: #1A1D29
- Text primary: #FFFFFF
- Text secondary: #A0AEC0
- Positive: #3B82F6
- Negative: #EF4444
- Neutral: #6B7280
- Border: #2D3748

## 4. Refresh + caching
- UI refresh every 5 seconds
- Cache DB reads at 5 seconds
- Cache NWS temps at 5 minutes

## 5. Trade display policy
- Show exact trades with a 60-minute delay.
- Do not display internal order IDs.
- Timestamps rounded to minute for public view.

---
