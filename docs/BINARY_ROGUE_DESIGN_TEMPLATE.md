# Binary Rogue Design System Template

> **Universal Template for Binary Rogue Properties**
>
> Version 2.0 | Last Updated: February 2026

---

## Quick Start Checklist

When starting a new site, complete these steps:

- [ ] Copy the CSS foundation from this template
- [ ] Download Freckle Face font (or use base64 embed)
- [ ] Set your `{{SITE_NAME}}` and `{{SITE_SUBTITLE}}`
- [ ] Choose your tagline
- [ ] Configure color mode (standard or inverted)
- [ ] Select card variants for your use case
- [ ] Test responsive breakpoints

---

## Table of Contents

1. [Header System](#1-header-system)
2. [Color Palette](#2-color-palette)
3. [Typography](#3-typography)
4. [Component Library](#4-component-library)
5. [Card Variants](#5-card-variants)
6. [Status Bar System](#6-status-bar-system)
7. [Responsive Design](#7-responsive-design)
8. [CSS Foundation](#8-css-foundation)
9. [Implementation Examples](#9-implementation-examples)
10. [Customization Guide](#10-customization-guide)

---

## 1. Header System

### Structure (Exact Duplication Required)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  [LOGO]              {{SITE_NAME}}                        [CLOCK]           │
│  180px            {{SITE_SUBTITLE}}                    HH:MM AM TZ          │
│                 "{{TAGLINE}}"                                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layout Columns

| Column | Width | Content | Alignment |
|--------|-------|---------|-----------|
| Left | 1fr | Logo (180px max) | Left |
| Center | 2fr | Site name, subtitle, tagline | Center |
| Right | 1fr | Live clock | Right |

### Header HTML Template

```html
<div class="br-header">
    <div class="br-header-left">
        <img src="{{LOGO_PATH}}" class="br-logo" alt="{{SITE_NAME}}" />
    </div>

    <div class="br-header-center">
        <div class="br-site-name">{{SITE_NAME}}</div>
        <div class="br-site-subtitle">{{SITE_SUBTITLE}}</div>
        <div class="br-tagline">"{{TAGLINE}}"</div>
    </div>

    <div class="br-header-right">
        <div class="br-clock" id="live-clock">
            <span class="br-clock-time">12:00 PM</span>
            <span class="br-clock-tz">EST</span>
        </div>
    </div>
</div>
```

### Clock JavaScript

```javascript
function updateClock() {
    const now = new Date();
    const options = {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
        timeZone: 'America/New_York'
    };
    const timeStr = now.toLocaleTimeString('en-US', options);
    const isDST = now.getTimezoneOffset() < new Date(now.getFullYear(), 0, 1).getTimezoneOffset();
    const tzAbbrev = isDST ? 'EDT' : 'EST';

    document.querySelector('.br-clock-time').textContent = timeStr;
    document.querySelector('.br-clock-tz').textContent = tzAbbrev;
}

// Update every second
setInterval(updateClock, 1000);
updateClock();
```

---

## 2. Color Palette

### Core Colors (18 Total)

#### Backgrounds (3)

| Variable | Hex | Name | Usage |
|----------|-----|------|-------|
| `--br-bg-deep` | `#0a0a0a` | Deep Black | Page background |
| `--br-bg-darker` | `#0d1117` | Darker Black | Secondary surfaces, strips |
| `--br-bg-card` | `#1a1f2e` | Dark Slate Blue | All card backgrounds |

#### Structure (2)

| Variable | Hex | Name | Usage |
|----------|-----|------|-------|
| `--br-border` | `#2d333b` | Border Gray | Borders, dividers |
| `--br-separator` | `#4b5563` | Separator Gray | Pipes, vertical dividers |

#### Text (4)

| Variable | Hex | Name | Usage |
|----------|-----|------|-------|
| `--br-text-white` | `#ffffff` | Pure White | Maximum contrast text |
| `--br-text-primary` | `#fafafa` | Off White | Headlines, titles |
| `--br-text-muted` | `#94a3b8` | Slate Gray | Site name (Freckle Face) |
| `--br-text-secondary` | `#6b7280` | Medium Gray | Labels, metadata, captions |

#### Brand Accent (4)

| Variable | Hex | Name | Usage |
|----------|-----|------|-------|
| `--br-accent-cyan-green` | `#00ffc8` | Cyan Green | Primary accent, gradient start |
| `--br-accent-cyan` | `#00d9ff` | Bright Cyan | Values, stats, gradient mid |
| `--br-accent-purple` | `#a78bfa` | Purple | Secondary accent, gradient end |
| `--br-accent-blue` | `#1e90ff` | Dodger Blue | Tagline, links |

#### Status (5)

| Variable | Hex | Name | Usage |
|----------|-----|------|-------|
| `--br-status-info` | `#06b6d4` | Cyan | Info, primary actions |
| `--br-status-success` | `#10b981` | Success Green | Success, positive, live |
| `--br-status-warning` | `#f59e0b` | Amber | Warnings, caution |
| `--br-status-alert` | `#f97316` | Orange | Alerts, important notices |
| `--br-status-error` | `#ef4444` | Error Red | Errors, negative, critical |

### Brand Gradient

```css
/* Primary gradient - use on subtitles */
background: linear-gradient(90deg, #00ffc8, #00d9ff, #a78bfa);
-webkit-background-clip: text;
-webkit-text-fill-color: transparent;
background-clip: text;
```

**Gradient Stops:**
- 0% → `#00ffc8` (Cyan Green)
- 50% → `#00d9ff` (Bright Cyan)
- 100% → `#a78bfa` (Purple)

---

## 3. Typography

### Font Stack

| Font | Source | Usage | Weights |
|------|--------|-------|---------|
| **Freckle Face** | Local WOFF2 | Site name ONLY | normal |
| **Inter** | Google Fonts | Subtitles, body, UI | 400, 500, 600, 700, 800 |
| **JetBrains Mono** | Google Fonts | Tagline, code, timestamps | 400, 500, 600 |

### Type Scale

| Element | Desktop | Mobile | Font | Weight | Color |
|---------|---------|--------|------|--------|-------|
| Site Name | 56px | 40px | Freckle Face | normal | `#94a3b8` |
| Subtitle | 42px | 28px | Inter | 800 | gradient |
| Tagline | 22px | 15px | JetBrains Mono | 600 | `#1e90ff` |
| Section Header | 20px | 18px | Inter | 600 | `#fafafa` |
| Card Title | 15px | 14px | Inter | 700 | `#fafafa` |
| Card Value (large) | 28px | 24px | Inter | 700 | `#00ffc8` |
| Stat Value | 13px | 14px | Inter | 600 | `#00d9ff` |
| Stat Label | 9px | 10px | Inter | normal | `#6b7280` |
| Body Text | 14px | 14px | Inter | 400 | `#fafafa` |
| Caption/Meta | 12px | 12px | Inter | 400 | `#6b7280` |
| Clock | 15px | 13px | JetBrains Mono | 600 | `#10b981` |

### Font Loading

```html
<!-- Google Fonts -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

```css
/* Local Freckle Face - embed base64 for reliability */
@font-face {
    font-family: 'Freckle Face';
    src: url('path/to/freckle-face.woff2') format('woff2');
    font-weight: normal;
    font-style: normal;
    font-display: swap;
}
```

---

## 4. Component Library

### Base Card

All cards share this foundation:

```css
.br-card {
    background: var(--br-bg-card);        /* #1a1f2e */
    border: 1px solid var(--br-border);   /* #2d333b */
    border-radius: 8px;
    padding: 12px;
    margin-bottom: 8px;
}
```

### Stat Grid (Inside Cards)

```css
.br-stat-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 4px 8px;
}

.br-stat-label {
    font-size: 9px;
    color: var(--br-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.br-stat-value {
    font-size: 13px;
    font-weight: 600;
    color: var(--br-accent-cyan);
}
```

### Strip Component

Horizontal summary bar:

```css
.br-strip {
    background: var(--br-bg-darker);      /* #0d1117 */
    border: 1px solid var(--br-bg-card);  /* #1a1f2e */
    border-radius: 6px;
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
}
```

---

## 5. Card Variants

### Standard Card (Dashboard/Stats)

```html
<div class="br-card">
    <div class="br-card-title">New York</div>
    <div class="br-card-value">72°F</div>
    <div class="br-stat-grid">
        <div class="br-stat">
            <span class="br-stat-label">Status</span>
            <span class="br-stat-value br-status-success">Active</span>
        </div>
        <div class="br-stat">
            <span class="br-stat-label">Updated</span>
            <span class="br-stat-value">2m ago</span>
        </div>
    </div>
</div>
```

### Link Card (News/Drudge Style)

Minimal card for URL links:

```html
<a href="{{URL}}" class="br-link-card">
    <div class="br-link-source">{{SOURCE}}</div>
    <div class="br-link-headline">{{HEADLINE}}</div>
    <div class="br-link-meta">
        <span class="br-link-time">{{TIME_AGO}}</span>
        <span class="br-link-category">{{CATEGORY}}</span>
    </div>
</a>
```

```css
.br-link-card {
    background: var(--br-bg-card);
    border: 1px solid var(--br-border);
    border-radius: 8px;
    padding: 12px 16px;
    display: block;
    text-decoration: none;
    transition: border-color 0.2s, transform 0.2s;
}

.br-link-card:hover {
    border-color: var(--br-accent-cyan);
    transform: translateY(-2px);
}

.br-link-source {
    font-size: 10px;
    color: var(--br-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}

.br-link-headline {
    font-size: 14px;
    font-weight: 600;
    color: var(--br-text-primary);
    line-height: 1.4;
    margin-bottom: 8px;
}

.br-link-meta {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--br-text-secondary);
}

.br-link-category {
    color: var(--br-accent-cyan);
}
```

### Article Card (Blog Style)

```html
<article class="br-article-card">
    <div class="br-article-image">
        <img src="{{IMAGE}}" alt="{{TITLE}}" />
    </div>
    <div class="br-article-content">
        <div class="br-article-category">{{CATEGORY}}</div>
        <h3 class="br-article-title">{{TITLE}}</h3>
        <p class="br-article-excerpt">{{EXCERPT}}</p>
        <div class="br-article-meta">
            <span class="br-article-author">{{AUTHOR}}</span>
            <span class="br-article-date">{{DATE}}</span>
        </div>
    </div>
</article>
```

```css
.br-article-card {
    background: var(--br-bg-card);
    border: 1px solid var(--br-border);
    border-radius: 8px;
    overflow: hidden;
}

.br-article-image img {
    width: 100%;
    height: 180px;
    object-fit: cover;
}

.br-article-content {
    padding: 16px;
}

.br-article-category {
    font-size: 10px;
    color: var(--br-accent-purple);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 8px;
}

.br-article-title {
    font-size: 18px;
    font-weight: 700;
    color: var(--br-text-primary);
    margin: 0 0 8px 0;
    line-height: 1.3;
}

.br-article-excerpt {
    font-size: 13px;
    color: var(--br-text-secondary);
    line-height: 1.5;
    margin: 0 0 12px 0;
}

.br-article-meta {
    display: flex;
    justify-content: space-between;
    font-size: 11px;
    color: var(--br-text-secondary);
}
```

### Metric Card (KPI Style)

```html
<div class="br-metric-card">
    <div class="br-metric-label">Total Users</div>
    <div class="br-metric-value">1,234</div>
    <div class="br-metric-change br-positive">+12.5%</div>
</div>
```

```css
.br-metric-card {
    background: var(--br-bg-card);
    border: 1px solid var(--br-border);
    border-radius: 8px;
    padding: 16px;
    text-align: center;
}

.br-metric-label {
    font-size: 11px;
    color: var(--br-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 8px;
}

.br-metric-value {
    font-size: 32px;
    font-weight: 700;
    color: var(--br-accent-cyan-green);
    line-height: 1;
    margin-bottom: 8px;
}

.br-metric-change {
    font-size: 13px;
    font-weight: 600;
}

.br-metric-change.br-positive { color: var(--br-status-success); }
.br-metric-change.br-negative { color: var(--br-status-error); }
```

---

## 6. Status Bar System

### Standard Status Bar

```html
<div class="br-status-bar">
    <div class="br-status-item br-status-alert">
        <span class="br-status-icon">🛡️</span>
        <span class="br-status-text">{{STATUS_MESSAGE}}</span>
    </div>
    <span class="br-status-divider">|</span>
    <div class="br-status-item br-status-live">
        <span class="br-status-dot">●</span>
        <span class="br-status-text">LIVE</span>
        <span class="br-status-time">{{TIME}}</span>
    </div>
</div>
```

```css
.br-status-bar {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 16px;
    padding: 8px 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 14px;
}

.br-status-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
}

.br-status-divider {
    color: var(--br-separator);
}

.br-status-alert { color: var(--br-status-alert); }
.br-status-live { color: var(--br-status-success); }

.br-status-dot {
    animation: pulse 2s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}
```

---

## 7. Responsive Design

### Breakpoints

| Breakpoint | Width | Target |
|------------|-------|--------|
| Desktop | > 1024px | Full layout |
| Tablet | 768px - 1024px | Adjusted spacing |
| Mobile | < 768px | Stacked, larger touch targets |

### Mobile Adjustments

```css
@media (max-width: 768px) {
    /* Container */
    .br-container {
        padding: 8px 12px;
    }

    /* Header */
    .br-header {
        flex-direction: column;
        gap: 12px;
    }

    .br-site-name { font-size: 40px; }
    .br-site-subtitle { font-size: 28px; letter-spacing: 1px; }
    .br-tagline { font-size: 15px; }

    /* Cards */
    .br-card { padding: 10px; }
    .br-card-title { font-size: 14px; }
    .br-card-value { font-size: 24px; }
    .br-stat-label { font-size: 10px; }
    .br-stat-value { font-size: 14px; }

    /* Grid collapses to single column or 2-up */
    .br-grid {
        grid-template-columns: 1fr;
    }

    .br-grid-2up {
        grid-template-columns: repeat(2, 1fr);
    }

    /* Status bar wraps */
    .br-status-bar {
        flex-direction: column;
        gap: 8px;
    }

    .br-status-divider {
        display: none;
    }
}
```

---

## 8. CSS Foundation

### Complete CSS Variables

```css
:root {
    /* ===== BACKGROUNDS ===== */
    --br-bg-deep: #0a0a0a;
    --br-bg-darker: #0d1117;
    --br-bg-card: #1a1f2e;

    /* ===== STRUCTURE ===== */
    --br-border: #2d333b;
    --br-separator: #4b5563;

    /* ===== TEXT ===== */
    --br-text-white: #ffffff;
    --br-text-primary: #fafafa;
    --br-text-muted: #94a3b8;
    --br-text-secondary: #6b7280;

    /* ===== BRAND ACCENT ===== */
    --br-accent-cyan-green: #00ffc8;
    --br-accent-cyan: #00d9ff;
    --br-accent-purple: #a78bfa;
    --br-accent-blue: #1e90ff;

    /* ===== STATUS ===== */
    --br-status-info: #06b6d4;
    --br-status-success: #10b981;
    --br-status-warning: #f59e0b;
    --br-status-alert: #f97316;
    --br-status-error: #ef4444;

    /* ===== SPACING ===== */
    --br-space-xs: 4px;
    --br-space-sm: 8px;
    --br-space-md: 12px;
    --br-space-lg: 16px;
    --br-space-xl: 24px;
    --br-space-2xl: 32px;

    /* ===== RADII ===== */
    --br-radius-sm: 4px;
    --br-radius-md: 6px;
    --br-radius-lg: 8px;
    --br-radius-xl: 12px;

    /* ===== SHADOWS ===== */
    --br-shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.3);
    --br-shadow-md: 0 4px 8px rgba(0, 0, 0, 0.4);
    --br-shadow-lg: 0 8px 16px rgba(0, 0, 0, 0.5);

    /* ===== TRANSITIONS ===== */
    --br-transition-fast: 0.15s ease;
    --br-transition-normal: 0.2s ease;
    --br-transition-slow: 0.3s ease;
}
```

### Base Reset & Globals

```css
/* Reset */
*, *::before, *::after {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

/* Base */
html {
    font-size: 16px;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background-color: var(--br-bg-deep);
    color: var(--br-text-primary);
    line-height: 1.5;
    min-height: 100vh;
}

/* Container */
.br-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 12px 20px;
}

/* Links */
a {
    color: var(--br-accent-cyan);
    text-decoration: none;
    transition: color var(--br-transition-fast);
}

a:hover {
    color: var(--br-accent-cyan-green);
}

/* Selection */
::selection {
    background: var(--br-accent-purple);
    color: var(--br-bg-deep);
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: var(--br-bg-darker);
}

::-webkit-scrollbar-thumb {
    background: var(--br-border);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--br-separator);
}
```

### Complete Header CSS

```css
/* Header Layout */
.br-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 0;
    gap: 20px;
}

.br-header-left,
.br-header-right {
    flex: 1;
}

.br-header-center {
    flex: 2;
    text-align: center;
}

.br-header-right {
    text-align: right;
}

/* Logo */
.br-logo {
    max-width: 180px;
    height: auto;
}

/* Site Name - Freckle Face */
.br-site-name {
    font-family: 'Freckle Face', cursive;
    font-size: 56px;
    color: var(--br-text-muted);
    line-height: 1;
    margin-bottom: 4px;
}

/* Subtitle - Gradient */
.br-site-subtitle {
    font-family: 'Inter', sans-serif;
    font-size: 42px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 2px;
    background: linear-gradient(90deg, #00ffc8, #00d9ff, #a78bfa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1;
    margin-bottom: 8px;
}

/* Tagline */
.br-tagline {
    font-family: 'JetBrains Mono', monospace;
    font-size: 22px;
    font-style: italic;
    font-weight: 600;
    color: var(--br-accent-blue);
    line-height: 1.2;
}

/* Clock */
.br-clock {
    font-family: 'JetBrains Mono', monospace;
    font-size: 15px;
    color: var(--br-status-success);
    font-weight: 600;
}

.br-clock-tz {
    color: var(--br-text-secondary);
    margin-left: 4px;
}
```

---

## 9. Implementation Examples

### Example 1: News Aggregator (Drudge Style)

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Binary Wire</title>
    <!-- Fonts & Styles -->
</head>
<body>
    <div class="br-container">
        <header class="br-header">
            <div class="br-header-left">
                <img src="logo.png" class="br-logo" alt="Binary Wire" />
            </div>
            <div class="br-header-center">
                <div class="br-site-name">Binary Wire</div>
                <div class="br-site-subtitle">NEWS TERMINAL</div>
                <div class="br-tagline">"Information Wants To Be Free"</div>
            </div>
            <div class="br-header-right">
                <div class="br-clock" id="live-clock">
                    <span class="br-clock-time">12:00 PM</span>
                    <span class="br-clock-tz">EST</span>
                </div>
            </div>
        </header>

        <div class="br-status-bar">
            <div class="br-status-item br-status-alert">
                ⚡ BREAKING NEWS
            </div>
            <span class="br-status-divider">|</span>
            <div class="br-status-item br-status-live">
                ● LIVE FEED
            </div>
        </div>

        <main class="br-grid br-grid-3col">
            <a href="#" class="br-link-card">
                <div class="br-link-source">Reuters</div>
                <div class="br-link-headline">Major Development in Tech Sector...</div>
                <div class="br-link-meta">
                    <span class="br-link-time">5m ago</span>
                    <span class="br-link-category">Tech</span>
                </div>
            </a>
            <!-- More cards... -->
        </main>
    </div>
</body>
</html>
```

### Example 2: Dashboard

```html
<main class="br-grid br-grid-4col">
    <div class="br-metric-card">
        <div class="br-metric-label">Total Users</div>
        <div class="br-metric-value">12,847</div>
        <div class="br-metric-change br-positive">+8.3%</div>
    </div>

    <div class="br-metric-card">
        <div class="br-metric-label">Revenue</div>
        <div class="br-metric-value">$48.2K</div>
        <div class="br-metric-change br-positive">+12.1%</div>
    </div>

    <div class="br-metric-card">
        <div class="br-metric-label">Active Now</div>
        <div class="br-metric-value">847</div>
        <div class="br-metric-change br-negative">-2.4%</div>
    </div>

    <div class="br-metric-card">
        <div class="br-metric-label">Conversion</div>
        <div class="br-metric-value">3.2%</div>
        <div class="br-metric-change br-positive">+0.8%</div>
    </div>
</main>
```

### Example 3: Blog

```html
<main class="br-grid br-grid-3col">
    <article class="br-article-card">
        <div class="br-article-image">
            <img src="post-image.jpg" alt="Article" />
        </div>
        <div class="br-article-content">
            <div class="br-article-category">Technology</div>
            <h3 class="br-article-title">The Future of AI Agents</h3>
            <p class="br-article-excerpt">Exploring how autonomous systems are reshaping...</p>
            <div class="br-article-meta">
                <span class="br-article-author">Binary Rogue</span>
                <span class="br-article-date">Feb 1, 2026</span>
            </div>
        </div>
    </article>
    <!-- More articles... -->
</main>
```

---

## 10. Customization Guide

### Changing the Site Identity

1. **Site Name**: Replace `{{SITE_NAME}}` in HTML
2. **Subtitle**: Replace `{{SITE_SUBTITLE}}` in HTML
3. **Tagline**: Replace `{{TAGLINE}}` - keep it short, punchy
4. **Logo**: Replace `{{LOGO_PATH}}` - use 180px max width

### Suggested Taglines

| Type | Example |
|------|---------|
| News | "Information Wants To Be Free" |
| Dashboard | "Data Never Sleeps" |
| Blog | "Thoughts From The Edge" |
| Finance | "Alpha In The Chaos" |
| Tech | "Build Different. Think Dangerous." |
| General | "Glitch The System. Burn The Map." |

### Color Variations

You can create themed variants by overriding accent colors:

```css
/* Cyberpunk variant */
:root {
    --br-accent-cyan-green: #ff00ff;
    --br-accent-cyan: #00ffff;
    --br-accent-purple: #ff6b6b;
}

/* Minimal variant */
:root {
    --br-accent-cyan-green: #ffffff;
    --br-accent-cyan: #ffffff;
    --br-accent-purple: #ffffff;
}

/* Warm variant */
:root {
    --br-accent-cyan-green: #f59e0b;
    --br-accent-cyan: #f97316;
    --br-accent-purple: #ef4444;
}
```

### Grid Utilities

```css
.br-grid {
    display: grid;
    gap: var(--br-space-lg);
}

.br-grid-2col { grid-template-columns: repeat(2, 1fr); }
.br-grid-3col { grid-template-columns: repeat(3, 1fr); }
.br-grid-4col { grid-template-columns: repeat(4, 1fr); }
.br-grid-5col { grid-template-columns: repeat(5, 1fr); }

/* Auto-fit responsive */
.br-grid-auto {
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}
```

---

## Files Checklist

When setting up a new site, ensure you have:

```
your-site/
├── index.html
├── css/
│   └── binary-rogue.css       # Copy from this template
├── js/
│   └── clock.js               # Live clock script
├── fonts/
│   └── freckle-face.woff2     # Required for site name
└── assets/
    └── logo.png               # Your site logo (180px max)
```

---

## Quick Copy: Minimal HTML Boilerplate

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{SITE_NAME}} - {{SITE_SUBTITLE}}</title>

    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">

    <!-- Styles -->
    <link rel="stylesheet" href="css/binary-rogue.css">
</head>
<body>
    <div class="br-container">
        <!-- HEADER -->
        <header class="br-header">
            <div class="br-header-left">
                <img src="assets/logo.png" class="br-logo" alt="{{SITE_NAME}}" />
            </div>
            <div class="br-header-center">
                <div class="br-site-name">{{SITE_NAME}}</div>
                <div class="br-site-subtitle">{{SITE_SUBTITLE}}</div>
                <div class="br-tagline">"{{TAGLINE}}"</div>
            </div>
            <div class="br-header-right">
                <div class="br-clock" id="live-clock">
                    <span class="br-clock-time">--:-- --</span>
                    <span class="br-clock-tz">EST</span>
                </div>
            </div>
        </header>

        <!-- STATUS BAR -->
        <div class="br-status-bar">
            <div class="br-status-item br-status-live">
                <span class="br-status-dot">●</span>
                <span>LIVE</span>
            </div>
        </div>

        <!-- MAIN CONTENT -->
        <main class="br-grid br-grid-auto">
            <!-- Your cards here -->
        </main>

        <!-- FOOTER -->
        <footer class="br-footer">
            <div class="br-footer-brand">Binary Rogue</div>
            <div class="br-footer-tagline">"Glitch The System. Burn The Map."</div>
        </footer>
    </div>

    <!-- Clock Script -->
    <script src="js/clock.js"></script>
</body>
</html>
```

---

<div align="center">

**Binary Rogue Design System**

*Glitch The System. Burn The Map.*

Template v2.0 | February 2026

</div>
