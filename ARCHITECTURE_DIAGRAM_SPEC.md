# Tech Spec: Rebuild `architecture.drawio`

## Objective

Replace the current `architecture.drawio` with a more technically complete diagram that reflects the actual system implementation. The current diagram merges zones, omits the coexistence deployment model, and lacks cross-cutting concerns. The new diagram should read as a real system architecture — not a pitch slide.

## Canvas & Style

- **Canvas:** ~1600×1000, white background, no page borders
- **Font family:** Google Sans, Roboto, Arial (consistent with current)
- **Color system (keep current):**
  - Internal boundary: `#EEF3FC` fill, `#4285F4` stroke
  - External boundary: `#FDF8EC` fill, `#F9AB00` stroke  
  - Human gates: `#FCE8E6` fill, `#EA4335` stroke
  - Success/validated: `#E6F4EA` fill, `#34A853` stroke
  - AI agent cards: white fill, `#DADCE0` stroke, drop shadow
  - Firewall: `#EA4335` solid fill
  - Cross-cutting bar: `#F3E8FD` fill, `#9334E6` stroke (new — purple for observability)
- **Arrows:**
  - Forward flow: `#34A853`, strokeWidth 2, blockThin endArrow
  - Feedback/reject: `#EA4335`, strokeWidth 1.5, dashed (6 3), blockThin
  - Data annotation: `#5F6368`, strokeWidth 1
  - Firewall crossing: `#EA4335`, strokeWidth 2.5

## Layout (top to bottom, left to right)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Title bar                                                          │
├────────────────────┬──────┬─────────────────────┬───────────────────┤
│  INTERNAL NETWORK  │      │  EXTERNAL AI        │                   │
│                    │  F   │                      │                   │
│  Zone 1: Legacy    │  I   │  Zone 4: Generation  │                   │
│  Zone 2: Analysis  │  R   │  Zone 5: Testing     │                   │
│  Zone 3: Strainer  │  E   │                      │                   │
│  ┌──────────┐      │  W   │                      │                   │
│  │ Gate 1   │      │  A   │  ┌──────────┐        │                   │
│  └──────────┘      │  L   │  │ Gate 2   │        │                   │
│  [Validated Spec]──│──L──→│  └──────────┘        │                   │
│                    │      │                      │                   │
├────────────────────┴──────┴──────────────────────┴───────────────────┤
│  Zone 6: Coexistence Deployment Model                                │
│  [Gate 3] → Shadow → Canary → Graduated → Full Production           │
├──────────────────────────────────────────────────────────────────────┤
│  Cross-Cutting: Audit Trail · Decisions DB · Telemetry               │
├──────────────────────────────────────────────────────────────────────┤
│  Legend                                                              │
└──────────────────────────────────────────────────────────────────────┘
```

## Detailed Element Specifications

### Title Block
- **Title:** `Initiative Zero — System Architecture`
- **Subtitle:** `Business rules in → New application out · No code translation · Zero tech debt carried forward`
- Position: top-left, y=16

### Internal Network Boundary (left column)
- Dashed rounded rect, `#EEF3FC` fill, `#4285F4` stroke, dashPattern `8 4`
- Label: `INTERNAL NETWORK — proprietary code never leaves`
- Contains Zones 1, 2, 3 and Human Gate 1

#### Zone 1: Legacy Environment
- White card with shadow
- Title: `Zone 1 · Legacy Environment`
- Subtitle: `Read-only access to source, DB, telemetry, audit logs`
- Sub-chips (small rounded rects inside): `Source Code`, `Database`, `Telemetry`, `Audit Logs`
- Footer text: `COBOL · Java · Ruby · Python · JCL · VSAM`

#### Zone 2: Analysis Engine
- White card with shadow
- Robot icon `🤖` + title: `Zone 2 · Analysis Engine`
- Subtitle: `Explainer Agent — deep comprehension and risk scoring`
- Two sub-steps as blue chips side by side with arrow between:
  1. `Comprehension` — "Dependency maps, debt assessment, dead code, security scan"
  2. `Confidence Scoring` — "Weighted rubric: clarity, extractability, coverage, isolation, complexity"
- Output annotation: `Analysis Report (JSON) → feeds Zone 3 enrichment`
- Include small text: `Cross-referenced against production telemetry (read-only)`

#### Zone 3: Business Rule Strainer
- White card with shadow
- Robot icon `🤖` + title: `Zone 3 · Business Rule Strainer`
- Subtitle: `Extractor Agent — distills business logic from implementation`
- Two sub-steps:
  1. `Rule Extraction` — "BR-### explicit rules, OBS-### behavioral observations"
  2. `Requirements Assembly` — "Technology-agnostic spec + Zone 2 enrichment appendix"
- Output: green validated box `✓ Validated Requirements Document`
- Below it: `Plain text only — zero variable names, zero schemas, zero source code`
- Small annotation showing enrichment flow arrow from Zone 2 into Zone 3's requirements assembly

#### Human Gate 1: Specification Sign-Off
- Red-bordered card between Zone 3 output and the firewall
- Icon: `👤`
- Title: `HUMAN GATE 1 · Specification Sign-Off`
- Body: `Domain expert validates extracted rules match business intent. Behavioral observations (OBS-*) require explicit SME confirmation.`
- Feedback loop arrow back to Zone 3: `Reject → re-extract`
- This is the **only** path to the firewall

### Security Firewall (center vertical bar)
- Solid red vertical rect, full height of the internal/external area
- Letters spelled vertically: `S E C U R I T Y`
- Annotation above: `Only plain-text requirements cross`
- Annotation below: `Blocked: source code, schemas, JCL, VSAM defs, API specs, variable names`
- Single arrow crossing from Validated Requirements to Zone 4: label `Requirements only`

### External AI Platform Boundary (right column)
- Dashed rounded rect, `#FDF8EC` fill, `#F9AB00` stroke
- Label: `EXTERNAL AI PLATFORM — no source code, no schemas, no IP`
- Contains Zones 4, 5 and Human Gate 2

#### Zone 4: Generation Engine
- White card with shadow
- Robot icon `🤖` + title: `Zone 4 · Generation Engine`
- Subtitle: `Generator Agent — greenfield application from requirements`
- Sub-chips: `Application Code`, `DB Adapter`, `Logging & Audit`
- Footer annotations:
  - `Each method traces to a named business rule (BR-###)`
  - `Any target language · Zero tech debt · AI-vendor agnostic`
- **Important:** No imports from internal — visually show this with a small "no source code" annotation

#### Zone 5: Testing Engine
- White card with shadow
- Robot icon `🤖` + title: `Zone 5 · Testing Engine`
- Subtitle: `Test Agent — generates tests from requirements, classifies drift`
- Drift classification chips (four colored):
  - Green: `Type 0 · Identical`
  - Blue: `Type 1 · Acceptable Variance`
  - Amber: `Type 2 · Semantic ⚠`
  - Red: `Type 3 · Breaking ✗`
- Quality Gate sub-box (green border):
  - `✓ 90%+ coverage`
  - `✓ Zero breaking drift`
  - `✓ All semantic adjudicated`
  - `✓ Security scan clean`
- Feedback loop from Quality Gate back to Zone 3 (crossing firewall): `Quality fail → re-extract rules`
- Executor annotation: `Subprocess sandbox · 10s timeout · isolated tmpdir`

#### Human Gate 2: Drift Adjudication
- Red-bordered card
- Icon: `👤`  
- Title: `HUMAN GATE 2 · Drift Adjudication`
- Body: `BA + Tech Lead classify semantic differences. Three outcomes: ACCEPT_VARIANCE, PRESERVE_BUG, ESCALATE_TO_COMPLIANCE`
- This feeds into Zone 6

### Zone 6: Coexistence Deployment Model (full-width bottom section)
- Spanning the full width below both internal and external boundaries
- Light background card with subtle border
- Title: `Zone 6 · Coexistence Deployment`

#### Sub-elements within Zone 6:

**Slice Progression Bar** (horizontal):
Five connected stages as a pipeline, left to right:
1. `Pure Logic` — green/completed style
2. `Boundary` — green/completed style
3. `Shadow` — amber/active style, "100% legacy serves, 100% modern shadows"
4. `Canary` — neutral, "97% legacy, 3% modern"
5. `Full Production` — neutral, "Legacy decommissioned"

**Coexistence Router Diagram** (below the progression bar):
```
         ┌─────────────┐
         │   Router     │
         └──────┬───────┘
           ┌────┴────┐
     ┌─────▼─────┐ ┌─▼──────────┐
     │  LEGACY    │ │  MODERN     │
     │  (serves)  │ │  (shadows)  │
     └─────┬─────┘ └─┬──────────┘
           └────┬────┘
         ┌──────▼───────┐
         │  Comparator   │
         │  Drift Check  │
         └───────────────┘
```
- Show this as actual diagram elements (not ASCII)
- Legacy box: green badge `■ LEGACY · SERVES TRAFFIC`
- Modern box: blue badge `□ MODERN · SHADOW (compare only)`
- Comparator: outputs drift classification
- Annotation: `Rollback instant at every stage`

**Human Gate 3: Production Authorization**
- Red-bordered card within Zone 6
- Icon: `👤`
- Title: `HUMAN GATE 3 · Production Authorization`
- Body: `Tech Lead sign-off required for each promotion. Shadow → Canary → Graduated → Full. Cannot be automated.`
- Feedback loop back to Testing: `Prod drift → re-classify`

**Post-deployment annotation:**
- Italic text: `Post-deployment: AI tools decommissioned. Standard code remains. Team shifts to monitoring → improvement.`

### Cross-Cutting Concerns Bar (below Zone 6)
- Purple-tinted horizontal bar spanning full width
- Title: `CROSS-CUTTING CONCERNS`
- Three sub-sections as chips:
  1. `Decisions Table` — "Every human gate decision: operator, timestamp, rationale, zone"
  2. `Audit Trail` — "Pipeline state machine: initiated → analyzed → extracted → approved → generated → tested → deployed"
  3. `Telemetry` — "Read-only production telemetry feeds Zone 2 analysis (PII-sanitized)"

### Legend Bar (bottom)
- Light gray background bar
- Items:
  - `🤖 AI Agent`
  - `👤 Human Decision Gate`
  - Red solid line: `Security Firewall`
  - Green solid line: `Forward flow`
  - Red dashed line: `Feedback / reject loop`
  - Purple: `Cross-cutting concern`
- Italicized footer: `Not code translation — generator receives requirements, not source. Zero tech debt carried forward.`

## Arrows / Flow Summary

| From | To | Style | Label |
|------|----|-------|-------|
| Zone 1 | Zone 2 | Green forward | `Source + telemetry` |
| Zone 2 | Zone 3 | Green forward | `Analysis report` |
| Zone 2 | Zone 3 (requirements assembly) | Blue data | `Enrichment appendix` |
| Zone 3 | Gate 1 | Green forward | |
| Gate 1 → reject | Zone 3 | Red dashed | `Reject → re-extract` |
| Gate 1 → approve | Validated Spec | Green forward | |
| Validated Spec | Firewall | Red crossing (2.5) | `Requirements only` |
| Firewall | Zone 4 | Red crossing (2.5) | |
| Zone 4 | Zone 5 | Green forward | `Generated code` |
| Zone 5 Quality Gate → fail | Zone 3 (via firewall) | Red dashed | `Quality fail → re-extract` |
| Zone 5 | Gate 2 | Green forward | |
| Gate 2 | Zone 6 | Green forward | |
| Zone 6 Gate 3 → reject | Zone 5 | Red dashed | `Prod drift → re-classify` |
| Zone 6 | Production | Green forward | |
| Decisions DB | All gates | Purple dotted | (implied, don't draw every line — just position it as underlying) |

## Implementation Notes for Claude Code

1. **Output format:** Single `.drawio` XML file (mxfile format compatible with draw.io / diagrams.net)
2. **Use the mxGraphModel structure** matching the existing file's format
3. **All text content must be XML-escaped** — use `&amp;` for `&`, etc.
4. **Keep cell IDs short and semantic** (e.g., `z1-legacy`, `z2-analysis`, `gate1`, `fw`, `z6-coex`)
5. **Test by opening in draw.io** — all elements should be visible and properly positioned without manual adjustment
6. **Canvas should not use page mode** (`page="0"`)
7. **Use shadow=1 on white cards** for depth
8. **Dashed boundaries use** `dashed=1;dashPattern=8 4`
9. **The diagram should be legible at 75% zoom** — minimum font size 8px for annotations, 11px for titles
10. **Group related elements** where possible for easier repositioning

## What NOT to Include

- No ROI numbers or cost estimates
- No specific technology vendor names (except as examples in Zone 1 language list)
- No marketing language
- No em dashes in labels (use `—` only in the title subtitle)
- No "Initiative Zero" branding beyond the title — this is a system diagram, not a deck slide

## Validation Checklist

- [ ] All 6 zones are labeled with zone numbers
- [ ] All 3 human gates are visually distinct (red border)
- [ ] Security firewall clearly separates internal/external
- [ ] Coexistence model shows shadow → canary → graduated → full
- [ ] Router diagram shows dual-path execution
- [ ] Cross-cutting concerns bar is present
- [ ] Feedback loops visible for all three failure scenarios (Gate 1 reject, Quality Gate fail, Prod drift)
- [ ] Enrichment flow from Zone 2 → Zone 3 is annotated
- [ ] Executor sandbox is mentioned in Zone 5
- [ ] No source code or implementation details leak into external zone visually
- [ ] Legend is complete
- [ ] Diagram opens cleanly in draw.io without overlapping elements

---

# UI Redesign Spec: `initiative-zero/static/`

## Design Direction

Move from the current gold/amber "hacker terminal" aesthetic toward a clean, high-contrast fintech engineering tool. Inspired by Wealthsimple's Dune (#32302F) + white palette but adapted for a dark-mode internal tool. The result should feel like a Bloomberg terminal designed by someone who cares about whitespace.

Keep the dark theme. Keep the engineering-tool feel. Strip the gold accent in favor of a more neutral warm palette that reads "premium fintech" rather than "crypto dashboard."

## Color Token Replacement

Replace the entire `:root` block in `style.css`:

```css
:root {
  /* ─── Base ─── */
  --bg:            #1a1918;      /* Warm dark, Dune-adjacent */
  --bg-surface:    #222120;      /* Card backgrounds */
  --bg-raised:     #2a2928;      /* Elevated elements, headers */
  --bg-hover:      #333231;      /* Hover states */
  --bg-active:     #3a3938;      /* Active/selected */

  /* ─── Borders ─── */
  --border:        #3a3938;
  --border-subtle: #2e2d2c;

  /* ─── Text ─── */
  --tx:            #f0edea;      /* Primary text — warm white */
  --tx2:           #a8a4a0;      /* Secondary */
  --tx3:           #787470;      /* Tertiary */
  --tx4:           #585450;      /* Muted labels */

  /* ─── Accent — warm neutral instead of gold ─── */
  --accent:        #e8e0d4;      /* Warm off-white for primary actions */
  --accent-dim:    #4a4640;      /* Accent backgrounds */
  --accent-hover:  #f5f0e8;      /* Button hover */

  /* ─── Semantic ─── */
  --green:         #2d9a6a;      /* Success, passing, approved */
  --green-dim:     rgba(45,154,106,.10);
  --green-tx:      #4fba8a;

  --amber:         #d4a24a;      /* Warning, pending, needs review */
  --amber-dim:     rgba(212,162,74,.10);
  --amber-tx:      #e8b960;

  --red:           #c44a3c;      /* Error, breaking, blocked */
  --red-dim:       rgba(196,74,60,.10);
  --red-tx:        #e86a5c;

  --blue:          #5a8ab8;      /* Info, acceptable variance */
  --blue-dim:      rgba(90,138,184,.10);
  --blue-tx:       #7aa8d0;

  --purple:        #8a6ab8;      /* Cross-cutting, audit */
  --purple-dim:    rgba(138,106,184,.10);
  --purple-tx:     #a88ad0;

  /* ─── Typography ─── */
  --mono: 'IBM Plex Mono', 'SF Mono', 'Fira Code', monospace;
  --sans: 'DM Sans', 'Inter', -apple-system, sans-serif;

  --sidebar-w: 240px;
}
```

### Key Differences from Current

| Token | Current | New | Rationale |
|-------|---------|-----|-----------|
| `--bg` | `#101113` (blue-black) | `#1a1918` (warm charcoal) | Warmer base, closer to Dune family |
| `--accent` | `#c9a55a` (gold) | `#e8e0d4` (warm off-white) | Less branded, more premium |
| `--green` | `#3d9a6e` | `#2d9a6a` | Slightly cooler, better contrast |
| `--red` | `#c25a4b` | `#c44a3c` | Slightly more saturated |
| New: `--purple` | n/a | `#8a6ab8` | For audit/cross-cutting elements |
| New: `--accent-hover` | n/a | `#f5f0e8` | Explicit hover state |

## Typography Changes

Replace Google Fonts import in `index.html`:

```html
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:ital,wght@0,300;0,400;0,500;0,600;1,400&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap" rel="stylesheet">
```

No change to font families — DM Sans + IBM Plex Mono is the right pairing. The current fonts are good.

## Component-Level Changes

### Sidebar

Current: Gold accent on active item indicator and logo.
New:

```css
.sidebar-logo {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--tx);           /* Was var(--accent) gold */
  margin-bottom: 2px;
}

.nav-item.active::before {
  /* ... */
  background: var(--tx);      /* Was var(--accent) — use warm white bar instead of gold */
}

.nav-item.active .nav-num {
  border-color: var(--tx3);
  color: var(--tx);
  background: var(--bg-active);  /* Was gold-tinted */
}
```

The sidebar should feel structural, not decorative. Active state uses the warm white text color as the indicator, not a brand color.

### Zone Tags

Current: Gold border and text.
New:

```css
.zone-tag {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .1em;
  text-transform: uppercase;
  color: var(--tx2);              /* Was gold */
  padding: 3px 7px;
  background: var(--bg-raised);   /* Was gold-tinted */
  border-radius: 3px;
  border: 1px solid var(--border);  /* Was gold border */
}
```

Zone tags should be quiet labels, not attention-grabbing badges.

### Primary Action Buttons (`.btn-advance`)

Current: Solid gold background with dark text.
New:

```css
.btn-advance {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  padding: 8px 18px;
  background: var(--accent);           /* Warm off-white */
  border: 1px solid var(--accent);
  color: var(--bg);                    /* Dark text on light button */
  border-radius: 4px;
  cursor: pointer;
  transition: all .15s;
  letter-spacing: .03em;
}
.btn-advance:hover {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
}
```

The primary CTA becomes a warm off-white button — high contrast against the dark background, reads as "premium" rather than "flashy."

### Code Viewer Language Badge

Current: Gold badge.
New:

```css
.code-lang {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--tx3);                    /* Was gold */
  padding: 2px 6px;
  background: var(--bg-hover);          /* Was gold-tinted */
  border-radius: 3px;
}
```

### Confidence Score Number

Current: Large white number.
New: Keep as-is, the `--tx` warm white works. No change needed.

### Firewall Divider

Current: Red dashes. Keep. The red firewall visual is semantically correct and shouldn't change.

### Human Gate Headers

Current: Amber background and text. Keep the amber semantic. This is correct — amber means "requires human action." No change.

### Status Chips

Keep the four semantic colors (green/blue/amber/red). These are functional, not decorative. The slight hue shifts in the new tokens are enough.

### Rubric Grid Scores

Current: Green/amber/red thresholds at 70/40.
New: Same thresholds, the new color tokens will handle the shift automatically.

### Data Cards (`.data-card-title .dot`)

Current: Green dot.
New:

```css
.data-card-title .dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--tx3);    /* Was var(--green) — neutral dot, not everything needs to be "passing" */
}
```

### Processing Indicator Dots

Current: Gold pulsing dots.
New:

```css
.processing-dots span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--tx2);    /* Was var(--accent) gold */
  animation: pulse 1.4s ease-in-out infinite;
}
```

### Toast Notifications

Current: Dark raised background. Keep — just inherits the new warmer background tokens.

### Coexistence Simulator

Keep all coexistence styles as-is. The green/blue legacy/modern badges are semantically correct. The router label using blue is correct. No changes needed to the coexistence section except inheriting the new base tokens.

## New Component: Pipeline Progress Indicator

Add a persistent horizontal progress indicator below the topbar showing the full pipeline state. This replaces the simple "Zone X of 6" badge.

```html
<!-- Add inside .topbar, replacing the badge -->
<div class="pipeline-progress">
  <div class="pp-step completed" data-zone="1"><span class="pp-num">1</span></div>
  <div class="pp-connector completed"></div>
  <div class="pp-step completed" data-zone="2"><span class="pp-num">2</span></div>
  <div class="pp-connector completed"></div>
  <div class="pp-step active" data-zone="3"><span class="pp-num">3</span></div>
  <div class="pp-connector"></div>
  <div class="pp-firewall-tick"></div>
  <div class="pp-connector"></div>
  <div class="pp-step" data-zone="4"><span class="pp-num">4</span></div>
  <div class="pp-connector"></div>
  <div class="pp-step" data-zone="5"><span class="pp-num">5</span></div>
  <div class="pp-connector"></div>
  <div class="pp-step" data-zone="6"><span class="pp-num">6</span></div>
</div>
```

```css
.pipeline-progress {
  display: flex;
  align-items: center;
  gap: 0;
  margin-left: auto;
}
.pp-step {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  background: transparent;
  cursor: pointer;
}
.pp-step .pp-num {
  font-family: var(--mono);
  font-size: 9px;
  font-weight: 600;
  color: var(--tx4);
}
.pp-step.completed {
  border-color: var(--green);
  background: var(--green-dim);
}
.pp-step.completed .pp-num { color: var(--green-tx); }
.pp-step.active {
  border-color: var(--tx2);
  background: var(--bg-active);
}
.pp-step.active .pp-num { color: var(--tx); }
.pp-connector {
  width: 12px;
  height: 1px;
  background: var(--border);
}
.pp-connector.completed {
  background: var(--green);
}
.pp-firewall-tick {
  width: 2px;
  height: 14px;
  background: var(--red);
  margin: 0 2px;
  border-radius: 1px;
}
```

Update `app.js` to sync this progress indicator with zone navigation — when a zone completes, add `.completed` class to its step and the connector before the next step.

## Structural HTML Changes

### Remove the static sidebar system block

The current sidebar has:
```html
<div class="sidebar-system">
  <strong>System:</strong> CLAIMS_PROC<br>
  ...
</div>
```

Replace with a dynamic block that updates based on the selected file:

```html
<div class="sidebar-system" id="sidebar-system">
  <span class="sidebar-system-label">No system selected</span>
</div>
```

Update via JS when a file is selected:
```javascript
document.getElementById('sidebar-system').innerHTML =
  '<span class="sidebar-system-label">' + filename + '</span>' +
  '<span class="sidebar-system-meta">COBOL · Run ' + state.runId + '</span>';
```

### Remove hardcoded operator name from HTML

Current: `Operator: S. Chen (Staff Eng)` appears in multiple places.
Replace with a single constant at the top of `app.js`:

```javascript
const OPERATOR = { name: 'S. Chen', role: 'Staff Eng' };
```

Reference this constant everywhere. This makes the demo feel more like a real system with configurable user context.

## What NOT to Change

- **The dark theme itself.** Don't go light mode. Engineering tools are dark.
- **DM Sans + IBM Plex Mono.** This pairing is correct.
- **Semantic color assignments.** Green = success, amber = warning, red = error, blue = info. These are standard.
- **The firewall visual.** Red dashed lines and the solid red divider are the most important visual in the entire UI. Don't soften them.
- **The coexistence simulator layout.** The dual-panel router diagram works well. Just inherits new base tokens.
- **Human gate card structure.** The amber header + white body pattern is correct for "requires action."
- **Font sizes.** The current size scale (9px labels, 11px body, 13px titles, 18px zone titles) is appropriate for an information-dense tool.

## Summary of Visual Impact

| Element | Before | After |
|---------|--------|-------|
| Overall warmth | Cool blue-black | Warm charcoal (Dune family) |
| Accent color | Gold (#c9a55a) | Warm off-white (#e8e0d4) |
| Brand feeling | "Crypto dashboard" | "Fintech internal tool" |
| Sidebar indicator | Gold bar | White bar |
| Primary button | Solid gold | Warm off-white |
| Zone tags | Gold badges | Quiet neutral labels |
| Processing dots | Gold pulse | Neutral gray pulse |
| New elements | None | Pipeline progress bar, purple audit color |

The goal: someone at Wealthsimple opens this and thinks "this could be one of our internal tools" rather than "someone styled a demo for us."
