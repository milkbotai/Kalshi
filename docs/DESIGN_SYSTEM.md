# MilkBot Design System

> **Binary Rogue** | Climate Exchange Dashboard | v1.0

---

## Overview

The MilkBot Design System defines the visual language for the Climate Exchange dashboard. This document serves as the single source of truth for colors, typography, components, and layout specifications.

**Key Files:**
- `src/dashboard/app.py` - Main dashboard styles
- `src/dashboard/assets/` - Logo and font assets
- `docs/DESIGN_SYSTEM.html` - Interactive color reference

---

## Color Palette

### 18 Colors Organized by Function

#### Backgrounds (3)

| Swatch | Hex | Name | Usage |
|--------|-----|------|-------|
| ![#0a0a0a](https://via.placeholder.com/20/0a0a0a/0a0a0a?text=+) | `#0a0a0a` | Deep Black | Main page background |
| ![#0d1117](https://via.placeholder.com/20/0d1117/0d1117?text=+) | `#0d1117` | Darker Black | Stats strip cards |
| ![#1a1f2e](https://via.placeholder.com/20/1a1f2e/1a1f2e?text=+) | `#1a1f2e` | Dark Slate Blue | All card backgrounds |

#### Structure (2)

| Swatch | Hex | Name | Usage |
|--------|-----|------|-------|
| ![#2d333b](https://via.placeholder.com/20/2d333b/2d333b?text=+) | `#2d333b` | Border Gray | Card borders, dividers |
| ![#4b5563](https://via.placeholder.com/20/4b5563/4b5563?text=+) | `#4b5563` | Separator Gray | Status bar pipes |

#### Text Primary (3)

| Swatch | Hex | Name | Usage |
|--------|-----|------|-------|
| ![#ffffff](https://via.placeholder.com/20/ffffff/ffffff?text=+) | `#ffffff` | Pure White | City codes (highest contrast) |
| ![#fafafa](https://via.placeholder.com/20/fafafa/fafafa?text=+) | `#fafafa` | Off White | City names, headlines |
| ![#94a3b8](https://via.placeholder.com/20/94a3b8/94a3b8?text=+) | `#94a3b8` | Slate Gray | "MilkBot" title only |

#### Text Secondary (1)

| Swatch | Hex | Name | Usage |
|--------|-----|------|-------|
| ![#6b7280](https://via.placeholder.com/20/6b7280/6b7280?text=+) | `#6b7280` | Medium Gray | Labels, metadata, HOLD signals |

#### Brand / Accent (4)

| Swatch | Hex | Name | Usage |
|--------|-----|------|-------|
| ![#00ffc8](https://via.placeholder.com/20/00ffc8/00ffc8?text=+) | `#00ffc8` | Cyan Green | Temperature values, gradient start |
| ![#00d9ff](https://via.placeholder.com/20/00d9ff/00d9ff?text=+) | `#00d9ff` | Bright Cyan | Stat values, gradient middle |
| ![#a78bfa](https://via.placeholder.com/20/a78bfa/a78bfa?text=+) | `#a78bfa` | Purple | Volume values, gradient end |
| ![#1e90ff](https://via.placeholder.com/20/1e90ff/1e90ff?text=+) | `#1e90ff` | Dodger Blue | Tagline text |

#### Signal / Status (5)

| Swatch | Hex | Name | Usage |
|--------|-----|------|-------|
| ![#06b6d4](https://via.placeholder.com/20/06b6d4/06b6d4?text=+) | `#06b6d4` | Cyan | BUY signals |
| ![#10b981](https://via.placeholder.com/20/10b981/10b981?text=+) | `#10b981` | Success Green | Positive P&L, tight spreads |
| ![#f59e0b](https://via.placeholder.com/20/f59e0b/f59e0b?text=+) | `#f59e0b` | Amber | Warnings, medium spreads |
| ![#f97316](https://via.placeholder.com/20/f97316/f97316?text=+) | `#f97316` | Orange | SELL signals |
| ![#ef4444](https://via.placeholder.com/20/ef4444/ef4444?text=+) | `#ef4444` | Error Red | Negative P&L, wide spreads |

---

## Brand Gradient

The signature gradient is used **exclusively** on the "CLIMATE EXCHANGE" title.

```
#00ffc8 ─────────────────────────────────────────── #a78bfa
   0%           #00d9ff           100%
                 50%
```

```css
background: linear-gradient(90deg, #00ffc8, #00d9ff, #a78bfa);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
background-clip: text;
```

---

## Typography

### Font Stack

| Font | Source | Usage |
|------|--------|-------|
| **Freckle Face** | Local (base64 WOFF2) | "MilkBot" title only |
| **Inter** | Google Fonts | Headlines, body text, UI |
| **JetBrains Mono** | Google Fonts | Tagline, status bar, code |

### Type Scale

| Element | Desktop | Mobile | Font | Weight | Color |
|---------|---------|--------|------|--------|-------|
| MilkBot Title | 56px | 40px | Freckle Face | normal | `#94a3b8` |
| CLIMATE EXCHANGE | 42px | 28px | Inter | 800 | gradient |
| Tagline | 22px | 15px | JetBrains Mono | 600 | `#1e90ff` |
| Section Headers | 20px | — | Inter | 600 | `#fafafa` |
| City Name | 15px | 14px | Inter | 700 | `#fafafa` |
| Temperature | 28px | 24px | Inter | 700 | `#00ffc8` |
| Stat Values | 13px | 14px | Inter | 600 | `#00d9ff` |
| Stat Labels | 9px | 10px | Inter | normal | `#6b7280` |

---

## Signal System

### Trading Signals

| Signal | Color | Hex | CSS Class |
|--------|-------|-----|-----------|
| **BUY** | Cyan | `#06b6d4` | `.signal-buy` |
| **SELL** | Orange | `#f97316` | `.signal-sell` |
| **HOLD** | Gray | `#6b7280` | `.signal-hold` |

### Spread Indicators

| Spread | Color | Hex | CSS Class |
|--------|-------|-----|-----------|
| Tight (1-2) | Green | `#10b981` | `.spread-tight` |
| Medium (3-4) | Amber | `#f59e0b` | `.spread-medium` |
| Wide (5+) | Red | `#ef4444` | `.spread-wide` |

### P&L States

| State | Color | Hex | CSS Class |
|-------|-------|-----|-----------|
| Positive | Green | `#10b981` | `.pnl-positive` |
| Negative | Red | `#ef4444` | `.pnl-negative` |

---

## Components

### City Card

```
┌─────────────────────────────┐
│       New York              │  ← #fafafa, 15px, 700
│         72°F                │  ← #00ffc8, 28px, 700
│                             │
│  SIGNAL  SPREAD  VOL  EDGE  │  ← #6b7280, 9px, uppercase
│   BUY     2¢    1.2K  +3.2% │  ← #00d9ff, 13px, 600
└─────────────────────────────┘
   bg: #1a1f2e
   border: 1px solid #2d333b
   radius: 8px
   padding: 12px 8px
```

### Stats Strip

```
┌──────────────────────────────────────────────────────┐
│  PORTFOLIO    TODAY      WIN RATE    TRADES         │
│   $1,542      +$42         68%        127           │
└──────────────────────────────────────────────────────┘
   bg: #0d1117
   border: 1px solid #1a1f2e
   radius: 6px
```

---

## Responsive Breakpoints

**Mobile:** `max-width: 768px`

| Property | Desktop | Mobile |
|----------|---------|--------|
| MilkBot title | 56px | 40px |
| CLIMATE EXCHANGE | 42px | 28px |
| Letter spacing | 2px | 1px |
| Tagline | 22px | 15px |
| City name | 15px | 14px |
| Temperature | 28px | 24px |
| Stat labels | 9px | 10px |
| Stat values | 13px | 14px |

---

## CSS Variables

```css
:root {
    /* Backgrounds */
    --bg-deep: #0a0a0a;
    --bg-darker: #0d1117;
    --bg-card: #1a1f2e;

    /* Structure */
    --border: #2d333b;
    --separator: #4b5563;

    /* Text */
    --text-white: #ffffff;
    --text-primary: #fafafa;
    --text-title: #94a3b8;
    --text-secondary: #6b7280;

    /* Brand */
    --accent-cyan-green: #00ffc8;
    --accent-cyan: #00d9ff;
    --accent-purple: #a78bfa;
    --accent-blue: #1e90ff;

    /* Signals */
    --signal-buy: #06b6d4;
    --signal-sell: #f97316;
    --signal-hold: #6b7280;

    /* Status */
    --success: #10b981;
    --warning: #f59e0b;
    --error: #ef4444;
}
```

---

## CSS Class Reference

### Header
- `.milkbot-title` — "MilkBot" (Freckle Face 56px #94a3b8)
- `.climate-title` — "CLIMATE EXCHANGE" (Inter 42px gradient)
- `.tagline` — Quote (JetBrains Mono 22px italic #1e90ff)

### Cards
- `.city-card` — Card container (bg #1a1f2e, border #2d333b)
- `.city-name-large` — City name (15px #fafafa 700)
- `.city-temp` — Temperature (28px #00ffc8 700)
- `.city-code` — City code (18px #ffffff 700)

### Stats
- `.stat-label` — Label (9px #6b7280 uppercase)
- `.stat-value` — Value (13px #00d9ff 600)
- `.volume-value` — Volume (13px #a78bfa)

---

## Source

- **Repository:** https://github.com/milkbotai/Kalshi
- **Primary File:** `src/dashboard/app.py`
- **Last Updated:** February 1, 2026

---

<div align="center">

**Binary Rogue**

*Glitch The System. Burn The Map.*

MilkBot — First AI Agent Hire

</div>
