# Initiative Zero — Design System Technical Spec

**Purpose:** Migrate the prototype UI (`initiative-zero/static/`) from the current dark theme to the light design system used in `architecture.drawio`. This document is the single source of truth for Claude Code to execute the reskin.

---

## 1. Design Tokens (CSS Custom Properties)

Replace the entire `:root` block in `style.css` with these tokens.

### 1.1 Surfaces & Backgrounds

```css
:root {
  /* Surfaces — Tailwind Gray scale */
  --bg:             #FFFFFF;       /* page background */
  --bg-surface:     #F9FAFB;       /* cards, panels, sidebar (gray-50) */
  --bg-raised:      #FFFFFF;       /* elevated cards on gray surface */
  --bg-hover:       #F3F4F6;       /* hover state (gray-100) */
  --bg-active:      #E5E7EB;       /* active/selected state (gray-200) */

  /* Borders */
  --border:         #E5E7EB;       /* primary border (gray-200) */
  --border-subtle:  #F3F4F6;       /* inner dividers (gray-100) */

  /* Firewall / dark accent */
  --bg-firewall:    #1F2937;       /* firewall bar fill (gray-800) */
  --bg-firewall-stroke: #111827;   /* firewall stroke (gray-900) */
```

### 1.2 Text Colors

```css
  /* Text hierarchy — light background */
  --tx:             #111827;       /* primary text (gray-900) */
  --tx2:            #4B5563;       /* secondary text (gray-600) */
  --tx3:            #9CA3AF;       /* tertiary / descriptions (gray-400) */
  --tx4:            #D1D5DB;       /* muted labels, metadata (gray-300) */
```

### 1.3 Semantic Colors (Status System)

Each semantic color has three tiers: a fill (background), a border/stroke, and a text/icon color.

```css
  /* Green — success, identical, AI badges, validated */
  --green:          #059669;       /* green-600 — text/icon */
  --green-border:   #BBF7D0;       /* green-200 — border */
  --green-fill:     #F0FDF4;       /* green-50  — background */

  /* Indigo — info, acceptable variance, modern system */
  --indigo:         #4F46E5;       /* indigo-600 — text/icon */
  --indigo-border:  #C7D2FE;       /* indigo-200 — border */
  --indigo-fill:    #EEF2FF;       /* indigo-50  — background */

  /* Amber — warning, semantic drift, needs review */
  --amber:          #D97706;       /* amber-600 — text/icon */
  --amber-border:   #FDE68A;       /* amber-200 — border */
  --amber-fill:     #FFFBEB;       /* amber-50  — background */

  /* Red — error, breaking drift, firewall labels */
  --red:            #DC2626;       /* red-600 — text/icon */
  --red-border:     #FECACA;       /* red-200 — border */
  --red-fill:       #FEF2F2;       /* red-50  — background */

  /* Human gate — dark badge on light surface */
  --human-badge-bg: #374151;       /* gray-700 */
  --human-badge-tx: #FFFFFF;
```

### 1.4 Accent / Brand

```css
  /* The drawio uses no gold accent — the visual hierarchy is
     carried entirely by the semantic colors above. If you want
     a subtle brand accent for the sidebar logo and zone tags,
     use indigo as the accent: */
  --accent:         #4F46E5;       /* indigo-600 */
  --accent-dim:     #EEF2FF;       /* indigo-50 */
```

### 1.5 Typography

```css
  /* Fonts — Inter replaces DM Sans to match the diagram */
  --sans: 'Inter', 'Helvetica Neue', Arial, sans-serif;
  --mono: 'IBM Plex Mono', monospace;

  /* Sidebar width */
  --sidebar-w: 240px;
}
```

### 1.6 Font Import

Replace the Google Fonts `<link>` in `index.html`:

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=IBM+Plex+Mono:ital,wght@0,300;0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">
```

---

## 2. Typography Scale

Extracted directly from the drawio `fontSize` and `fontStyle` attributes:

| Role | Size | Weight | Family | Color | Letter-spacing |
|---|---|---|---|---|---|
| Page title | 22px | 700 (bold) | `--sans` | `--tx` (#111827) | 0.5px |
| Page subtitle | 11px | 400 | `--sans` | `--tx3` (#9CA3AF) | — |
| Zone title | 13px | 700 (bold) | `--sans` | `--tx` (#111827) | — |
| Zone description | 9px | 400 | `--sans` | `--tx3` (#9CA3AF) | — |
| Gate title | 11px | 700 (bold) | `--sans` | `--tx` (#111827) | — |
| Gate description | 9px | 400 | `--sans` | `--tx3` (#9CA3AF) | — |
| Component label | 10px | 400 | `--sans` | `--tx2` (#4B5563) | — |
| Badge (AI) | 8px | 400 | `--sans` | `--green` (#059669) | — |
| Badge (HUMAN) | 8px | 400 | `--sans` | white | — |
| Section label / uppercase | 9px | 600 | `--sans` | `--tx3` (#9CA3AF) | 1px |
| Metadata / footnote | 8px | 400 | `--sans` | `--tx4` (#D1D5DB) | — |
| Italic footnote | 8px | 400 italic | `--sans` | `--tx4` (#D1D5DB) | — |
| Mono code / data | 11px | 400 | `--mono` | `--tx2` (#4B5563) | — |

---

## 3. Component Specifications

### 3.1 Zone Cards

The drawio represents each zone as a white rounded rectangle on the `--bg-surface` background.

```css
.zone-card {                         /* was .data-card */
  background: var(--bg-raised);      /* #FFFFFF */
  border: 1px solid var(--border);   /* #E5E7EB */
  border-radius: 8px;                /* arcSize=8 in drawio */
  padding: 14px 16px;
}
```

### 3.2 Sub-Components (pills inside zone cards)

```css
.zone-component {                    /* e.g. "Source Code", "Database" */
  background: var(--bg-surface);     /* #F9FAFB */
  border: 1px solid var(--border);   /* #E5E7EB */
  border-radius: 10px;               /* arcSize=10 */
  padding: 4px 12px;
  font-family: var(--sans);
  font-size: 10px;
  color: var(--tx2);                 /* #4B5563 */
}
```

### 3.3 AI Badge

```css
.badge-ai {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--green-fill);     /* #F0FDF4 */
  border: 1px solid var(--green-border); /* #BBF7D0 */
  border-radius: 10px;               /* arcSize=10 */
  font-family: var(--sans);
  font-size: 8px;
  color: var(--green);               /* #059669 */
  padding: 1px 6px;
  min-width: 26px;
  height: 16px;
}
```

### 3.4 Human Gate Badge

```css
.badge-human {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--human-badge-bg); /* #374151 */
  border: 1px solid var(--human-badge-bg);
  border-radius: 10px;
  font-family: var(--sans);
  font-size: 8px;
  color: var(--human-badge-tx);      /* #FFFFFF */
  padding: 1px 6px;
  min-width: 46px;
  height: 16px;
}
```

### 3.5 Human Gate Container

```css
.human-gate {
  border: 1.5px solid var(--human-badge-bg);  /* #374151, strokeWidth=1.5 */
  border-radius: 8px;
  overflow: hidden;
}
.human-gate-header {
  padding: 10px 14px;
  background: var(--bg-raised);                /* white */
  border-bottom: 1px solid var(--border);
  font-family: var(--sans);
  font-size: 11px;
  font-weight: 700;
  color: var(--tx);                            /* #111827 */
}
.human-gate-body {
  padding: 16px;
  background: var(--bg-raised);
}
.gate-desc {
  font-size: 9px;
  color: var(--tx3);                           /* #9CA3AF */
}
```

### 3.6 Drift Classification Chips

These four chip styles map directly to the drawio Type 0–3 nodes:

```css
/* Type 0 · Identical */
.drift-chip-0 {
  background: var(--green-fill);
  border: 1px solid var(--green-border);
  color: var(--green);
  border-radius: 12px;
  font-size: 9px;
  padding: 2px 8px;
}

/* Type 1 · Acceptable */
.drift-chip-1 {
  background: var(--indigo-fill);
  border: 1px solid var(--indigo-border);
  color: var(--indigo);
  border-radius: 12px;
  font-size: 9px;
  padding: 2px 8px;
}

/* Type 2 · Semantic */
.drift-chip-2 {
  background: var(--amber-fill);
  border: 1px solid var(--amber-border);
  color: var(--amber);
  border-radius: 12px;
  font-size: 9px;
  padding: 2px 8px;
}

/* Type 3 · Breaking */
.drift-chip-3 {
  background: var(--red-fill);
  border: 1px solid var(--red-border);
  color: var(--red);
  border-radius: 12px;
  font-size: 9px;
  padding: 2px 8px;
}
```

### 3.7 Quality Gate Bar

```css
.quality-gate-bar {
  background: var(--green-fill);     /* #F0FDF4 */
  border: 1px solid var(--green-border); /* #BBF7D0 */
  border-radius: 8px;
  padding: 10px 14px;
}
.quality-gate-bar .qg-title {
  font-size: 10px;
  font-weight: 700;
  color: var(--green);               /* #059669 */
}
.quality-gate-bar .qg-metric {
  font-size: 9px;
  color: var(--tx2);                 /* #4B5563 */
}
```

### 3.8 Firewall Divider

```css
.firewall-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 20px 0;
  padding: 10px 0;
}
.firewall-divider::before,
.firewall-divider::after {
  content: '';
  flex: 1;
  height: 2px;
  background: var(--bg-firewall);    /* #1F2937 — solid dark bar */
}
.firewall-divider span {
  font-family: var(--sans);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--tx3);                 /* #9CA3AF — not red in light mode */
  white-space: nowrap;
}
```

> **Note:** In the drawio, the firewall is a solid `#1F2937` rectangle with `#D1D5DB` text. It's authoritative and dark, not alarming red. The light-mode UI should match this: a dark stripe with neutral text.

### 3.9 Validated Requirements Document (highlight card)

```css
.validated-doc {
  background: var(--green-fill);
  border: 1px solid var(--green-border);
  border-radius: 10px;
  padding: 10px 16px;
  font-family: var(--sans);
  font-size: 11px;
  font-weight: 700;
  color: var(--green);
  text-align: center;
}
.validated-doc-note {
  font-size: 9px;
  color: var(--tx4);
  text-align: center;
  margin-top: 4px;
}
```

### 3.10 Slice Progression Bar (Zone 6)

```css
.slice-stage {
  background: var(--bg-raised);
  border-right: 1px solid var(--border);
  padding: 12px 10px;
  text-align: center;
}
.slice-stage.active {
  background: var(--amber-fill);     /* #FFFBEB */
}
.slice-stage.active .slice-stage-name {
  color: var(--amber);              /* #D97706 */
}
.slice-stage.completed {
  background: var(--green-fill);
}
.slice-stage.completed .slice-stage-name {
  color: var(--green);
}
```

### 3.11 Cross-Cutting Concerns Bar

```css
.cross-cutting-bar {
  background: var(--bg-surface);     /* #FAFAFA */
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 10px 14px;
}
.cross-cutting-bar .cc-label {
  font-family: var(--sans);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--tx3);
}
.cross-cutting-bar .cc-item {
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 4px 10px;
  font-size: 8px;
  color: var(--tx3);
}
.cross-cutting-bar .cc-item strong {
  color: var(--tx2);
}
```

### 3.12 Boundary Labels (Internal / External)

```css
.boundary-label {
  font-family: var(--sans);
  font-size: 9px;
  font-weight: 400;
  letter-spacing: 1px;
  color: var(--tx3);                 /* #9CA3AF */
  text-transform: uppercase;
}
/* "INTERNAL NETWORK — proprietary code never leaves" */
/* "EXTERNAL AI PLATFORM — no source code, no schemas, no IP" */
```

### 3.13 Sidebar

```css
.sidebar {
  background: var(--bg-raised);      /* #FFFFFF */
  border-right: 1px solid var(--border);
}
.sidebar-header {
  border-bottom: 1px solid var(--border);
}
.sidebar-logo {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);              /* #4F46E5 indigo */
}
.sidebar-system {
  background: var(--bg-surface);     /* #F9FAFB */
  border: 1px solid var(--border);
}
```

### 3.14 Buttons

```css
/* Primary action (advance) */
.btn-advance {
  background: var(--accent);         /* #4F46E5 */
  color: #FFFFFF;
  border: none;
  border-radius: 4px;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  padding: 8px 18px;
}
.btn-advance:hover {
  background: #4338CA;               /* indigo-700 */
}

/* Secondary */
.btn {
  background: var(--bg-raised);
  border: 1px solid var(--border);
  color: var(--tx2);
  border-radius: 4px;
}
.btn:hover {
  background: var(--bg-hover);
  border-color: #D1D5DB;
  color: var(--tx);
}

/* Semantic buttons */
.btn.green { border-color: var(--green-border); color: var(--green); }
.btn.green:hover { background: var(--green-fill); }
.btn.amber { border-color: var(--amber-border); color: var(--amber); }
.btn.amber:hover { background: var(--amber-fill); }
.btn.red { border-color: var(--red-border); color: var(--red); }
.btn.red:hover { background: var(--red-fill); }
```

---

## 4. Flow Indicators (Arrows / Connections)

Not rendered in HTML, but the color semantics should be preserved in any progress indicators or connecting lines:

| Flow Type | Color | Style | Drawio ref |
|---|---|---|---|
| Forward flow (happy path) | `#059669` (green-600) | Solid, 1.5px | `strokeColor=#059669; strokeWidth=1.5` |
| Firewall crossing | `#374151` (gray-700) | Solid, 2px | `strokeColor=#374151; strokeWidth=2` |
| Feedback loop (re-extract, re-classify) | `#9CA3AF` (gray-400) | Dashed `6 3` | `strokeDashPattern=6 3` |
| Edge labels | `#9CA3AF` (gray-400) | 8px Inter | `fontSize=8; fontColor=#9CA3AF` |

---

## 5. Boundary Containers

The drawio uses dashed boundaries for internal/external zones:

```css
.boundary-internal,
.boundary-external {
  border: 1px dashed var(--border);  /* dashPattern=8 4 */
  border-radius: 6px;
  background: var(--bg-surface);     /* #F9FAFB / #FAFAFA */
  padding: 20px;
}
```

---

## 6. Migration Mapping (Old → New)

Quick reference for the token swap. Every old token on the left maps to the new token on the right:

| Old Token (Dark Theme) | New Token (Light Theme) | Hex |
|---|---|---|
| `--bg: #101113` | `--bg: #FFFFFF` | white |
| `--bg-surface: #18191c` | `--bg-surface: #F9FAFB` | gray-50 |
| `--bg-raised: #1e2023` | `--bg-raised: #FFFFFF` | white |
| `--bg-hover: #252729` | `--bg-hover: #F3F4F6` | gray-100 |
| `--bg-active: #2a2d31` | `--bg-active: #E5E7EB` | gray-200 |
| `--border: #2a2d31` | `--border: #E5E7EB` | gray-200 |
| `--border-subtle: #222428` | `--border-subtle: #F3F4F6` | gray-100 |
| `--tx: #e8e6e3` | `--tx: #111827` | gray-900 |
| `--tx2: #9d9b97` | `--tx2: #4B5563` | gray-600 |
| `--tx3: #6b6966` | `--tx3: #9CA3AF` | gray-400 |
| `--tx4: #4a4845` | `--tx4: #D1D5DB` | gray-300 |
| `--accent: #c9a55a` | `--accent: #4F46E5` | indigo-600 |
| `--accent-dim: #8a7340` | `--accent-dim: #EEF2FF` | indigo-50 |
| `--green: #3d9a6e` | `--green: #059669` | green-600 |
| `--green-dim: rgba(61,154,110,.12)` | `--green-fill: #F0FDF4` | green-50 |
| `--green-tx: #5fbd8a` | `--green: #059669` | green-600 |
| `--amber: #c19a3e` | `--amber: #D97706` | amber-600 |
| `--amber-dim: rgba(193,154,62,.12)` | `--amber-fill: #FFFBEB` | amber-50 |
| `--amber-tx: #d4b15a` | `--amber: #D97706` | amber-600 |
| `--red: #c25a4b` | `--red: #DC2626` | red-600 |
| `--red-dim: rgba(194,90,75,.12)` | `--red-fill: #FEF2F2` | red-50 |
| `--red-tx: #e07363` | `--red: #DC2626` | red-600 |
| `--blue: #5a8ec2` | `--indigo: #4F46E5` | indigo-600 |
| `--blue-dim: rgba(90,142,194,.12)` | `--indigo-fill: #EEF2FF` | indigo-50 |
| `--blue-tx: #73a5d8` | `--indigo: #4F46E5` | indigo-600 |

> **Important:** The old theme collapsed text and icon colors into `-tx` variants (`--green-tx`, `--amber-tx`). The new system uses the base semantic color (`--green`, `--amber`) for both text and icons on light backgrounds, and separate `-fill` / `-border` tokens for container styling. The `-dim` tokens are replaced by `-fill` (solid hex, not rgba).

---

## 7. Renamed Token References in JS (`app.js`)

Search-and-replace these CSS variable references in `app.js`:

| Old Reference | New Reference |
|---|---|
| `var(--green-tx)` | `var(--green)` |
| `var(--amber-tx)` | `var(--amber)` |
| `var(--red-tx)` | `var(--red)` |
| `var(--blue-tx)` | `var(--indigo)` |
| `var(--green-dim)` | `var(--green-fill)` |
| `var(--amber-dim)` | `var(--amber-fill)` |
| `var(--red-dim)` | `var(--red-fill)` |
| `var(--blue-dim)` | `var(--indigo-fill)` |
| `var(--blue)` | `var(--indigo)` |

---

## 8. Code Viewer (Syntax Highlighting)

The current dark-theme syntax colors need to flip for readability on a light background:

```css
/* Light-mode syntax highlighting */
.kw   { color: #DC2626; }     /* keywords — red-600 */
.fn   { color: #4F46E5; }     /* functions — indigo-600 */
.str  { color: #059669; }     /* strings — green-600 */
.cmt  { color: #9CA3AF; font-style: italic; } /* comments — gray-400 */
.num  { color: #D97706; }     /* numbers — amber-600 */
.type { color: #7C3AED; }     /* types — violet-600 */
.op   { color: #4F46E5; }     /* operators — indigo-600 */
.dec  { color: #DC2626; }     /* declarations — red-600 */
```

Code viewer background:

```css
.code-body {
  background: var(--bg-surface);     /* #F9FAFB */
}
.code-body pre {
  color: var(--tx2);                 /* #4B5563 */
}
.code-header {
  background: var(--bg-surface);     /* #F9FAFB — was --bg-raised */
  border-bottom: 1px solid var(--border);
}
```

---

## 9. Body & Scrollbar

```css
html { font-size: 13px; }
body {
  font-family: var(--sans);
  background: var(--bg-surface);     /* #F9FAFB — page bg is the lightest gray */
  color: var(--tx);
  -webkit-font-smoothing: auto;      /* remove antialiasing override for light mode */
}

/* Light-mode scrollbars */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: var(--bg-surface); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #D1D5DB; }
```

---

## 10. Execution Checklist for Claude Code

1. **Replace the Google Fonts `<link>`** in `index.html` — swap DM Sans for Inter.
2. **Replace the `:root` block** in `style.css` with Section 1 tokens.
3. **Find-and-replace old token names** across `style.css` using Section 6 mapping. Pay attention to the `-tx` → base name and `-dim` → `-fill` renames.
4. **Find-and-replace JS references** in `app.js` using Section 7 mapping.
5. **Update syntax highlighting classes** (`.kw`, `.fn`, etc.) per Section 8.
6. **Update `body` styles** per Section 9.
7. **Update component-specific styles** (human gates, drift chips, quality gate, firewall divider, buttons) using Section 3 specs — these go beyond token swaps and may require structural CSS changes.
8. **Verify the toast, decision-record, and processing-dots** animations work against the light background. The processing dots should use `--accent` (#4F46E5) instead of the old gold.
9. **Test all six zones** end-to-end to confirm no dark-on-dark or light-on-light contrast issues remain.
10. **Sidebar active indicator** — change the left-edge accent bar from gold to `--accent` (#4F46E5).

---

*Spec extracted from `architecture.drawio` node styles. All hex values are from the Tailwind CSS default palette.*
