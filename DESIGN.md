---
name: ColdChain Rescue Design System ("OPS v2")
version: 2.0.0
last_updated: "2026-10-14"
framework: Next.js 14 + Tailwind CSS + MapLibre GL
contract_standards:
  - awesome-design-md
  - pbakaus/impeccable
  - taste-design-craft
tokens:
  surfaces:
    canvas: "#0a0a0b"
    surface_subtle: "#0e0e10"
    surface_raised: "#121214"
    surface_card: "#17171a"
    surface_top: "#1c2433"
    surface_inset: "#131316"
  borders:
    border: "#232326"
    border_strong: "#34343a"
    border_accent: "#2b5b8b"
    edge_light: "inset 0 1px 0 rgba(255, 255, 255, 0.07)"
  typography:
    display: "clamp(2.75rem, 5.5vw, 4.5rem)"
    h1: "clamp(1.75rem, 2.8vw, 2.5rem)"
    h2: "1.25rem"
    h3: "1.0625rem"
    body: "0.875rem"
    label: "0.75rem"
    micro: "0.6875rem"
    font_sans: "Inter, Segoe UI, sans-serif"
    font_mono: "JetBrains Mono, Menlo, monospace"
  thermal_spectrum:
    thermal_0: "#1e3a5f" # sub-zero / deep frozen (< -18°C)
    thermal_1: "#0ea5e9" # chilled (0°C)
    thermal_2: "#10b981" # nominal cold chain (4°C)
    thermal_3: "#84cc16" # upper boundary (8°C)
    thermal_4: "#f59e0b" # drifting warning (12°C)
    thermal_5: "#f97316" # breach warning (20°C)
    thermal_6: "#f43f5e" # critical breach / spoilage (> 40°C)
  motion:
    ease_out_expo: "cubic-bezier(0.16, 1, 0.3, 1)"
    ease_in_out_quint: "cubic-bezier(0.83, 0, 0.17, 1)"
    duration_fast: "140ms"
    duration_base: "260ms"
    duration_slow: "620ms"
    stagger: "60ms"
---

# ColdChain Rescue — Design System Specification ("OPS v2")

This document defines the formal visual design, interaction contracts, and token architecture for the **ColdChain Rescue** platform. It implements strict **Anti-Slop** design principles synthesized from `awesome-design-md`, `pbakaus/impeccable`, and `taste-design-craft`.

---

## 1. Design Philosophy & World-Building

ColdChain Rescue is not a consumer app or a generic SaaS template; it is a **mission-critical cold chain autonomous telemetry and rescue platform**. The interface is modeled after aerospace mission control and high-integrity data acquisition (DAQ) systems:

1. **Telemetry Over Decoration**: Every pixel conveys state, risk, or spatial location. Decorative gradients without semantic payload are strictly prohibited.
2. **Thermal Physicality**: Temperature is physical reality, not a subjective color choice. Every temperature visualization strictly references the calibrated 7-stop thermal spectrum.
3. **Deterministic Human-in-the-Loop Authority**: The UI draws a crystalline visual boundary between automated background inference (cyan telemetry) and irreversible physical actions (gold/warning gate requiring explicit operator clearance).
4. **Restrained Obsidian Surface Depth**: Deep obsidian backgrounds (`#0a0a0b` to `#17171a`) paired with razor-thin 1px hairlines and liquid depth radial sheens (`--depth-sheen`). Blurry drop shadows and milky light-halos are banned.

---

## 2. Token Architecture & Mathematical Scales

### A. Surface Palette & Depth Stack

Surfaces follow a strict luminosity stack from base canvas to topmost card:

| Token | Hex Value | Purpose |
| :--- | :--- | :--- |
| `--canvas` | `#0a0a0b` | Base application background (deep tinted obsidian, never flat #000000). |
| `--surface-subtle` | `#0e0e10` | Secondary backgrounds, inactive telemetry drawers. |
| `--surface-raised` | `#121214` | Section backgrounds, navigation rails, headers. |
| `--surface-card` | `#17171a` | Hairline operational cards, diagnostic panels. |
| `--surface-elevated` | `#1c2433` | Hover states, active modal dialogs, popovers. |
| `--surface-inset` | `#131316` | Telemetry track backgrounds, sunken metric grooves. |

### B. 7-Stop Thermal Spectrum

All temperature-bearing UI components (spines, gauge arcs, telemetry sparklines, route risk corridors) MUST map to this immutable scale:

```css
--thermal-0: #1e3a5f;   /* Frozen / Cryo (< -18°C) */
--thermal-1: #0ea5e9;   /* Chilled (0°C) */
--thermal-2: #10b981;   /* Nominal Cold Chain Safe Zone (+2°C to +8°C) */
--thermal-3: #84cc16;   /* Upper Warning Threshold (+8°C) */
--thermal-4: #f59e0b;   /* Drifting / Thermal Excursion (+12°C) */
--thermal-5: #f97316;   /* Excursion Breach (+20°C) */
--thermal-6: #f43f5e;   /* Critical Spoilage / Thermal Runaway (> +40°C) */
```

### C. 7-Step Typographic Scale

Type is strictly bounded to 7 programmatic steps. Arbitrary font sizes (`text-[15px]`, `text-[21px]`) are forbidden:

1. **Display** (`--t-display`): `clamp(2.75rem, 5.5vw, 4.5rem)` — Hero headings, system title.
2. **H1** (`--t-h1`): `clamp(1.75rem, 2.8vw, 2.5rem)` — Section titles.
3. **H2** (`--t-h2`): `1.25rem` — Card titles, facility names.
4. **H3** (`--t-h3`): `1.0625rem` — Sub-panel headers, modal titles.
5. **Body** (`--t-body`): `0.875rem` — Telemetry narratives, diagnostic reasoning.
6. **Label** (`--t-label`): `0.75rem` — Form labels, filter controls.
7. **Micro** (`--t-micro`): `0.6875rem` — DAQ mono eyebrows, status chips, timestamps.

*Rule: Tabular numerals (`font-variant-numeric: tabular-nums`) must be applied to all live telemetry values to prevent layout shifts.*

---

## 3. Strict Anti-Slop Banned Patterns (Enforced)

The following anti-patterns are banned across the repository:

1. ❌ **No AI Purple Gradients**: Generic `from-purple-500 to-indigo-600` styling is replaced by purposeful semantic accents: Cyan (`--ai: #06b6d4`) for system analysis, Emerald (`--nominal: #4b9d6f`) for validated health, Amber (`--accent: #d4a24c`) for human clearance.
2. ❌ **No Milky Inset Shadows**: `box-shadow: inset 0 1px 0 rgba(255,255,255,0.2)` is banned. Micro-highlights use `--edge-light: inset 0 1px 0 rgba(255, 255, 255, 0.07)`.
3. ❌ **No Hover Scale Jank on Lists**: Hovering cards in feed/table lists must use subtle vertical translation (`transform: translateY(-1px)`) rather than `scale(1.02)`, preventing 120Hz subpixel raster jitter.
4. ❌ **No Raw Unstyled Primitives**: All inputs and buttons must utilize standardized `.ops-card`, `.ops-button`, and semantic tokens.
5. ❌ **No Dead Frames or Faked Success**: Animation holds must contain living drift or telemetry pulses. Acceptance metrics must report live verified counts (143/143 tests).

---

## 4. Component Standards

### A. Numbered Section Eyebrows (`.ops-eyebrow`)
DAQ-style numbered markers with trailing hairline gradients:
```tsx
<div className="ops-eyebrow">
  <span className="ops-eyebrow__num">01</span>
  <span>FLEET TELEMETRY & DIGITAL TWIN</span>
</div>
```

### B. Thermal Spine (`.ops-spine`)
A 2px precision indicator tracking fleet-wide risk state dynamically:
```tsx
<div className="ops-spine">
  <div 
    className="ops-spine__fill" 
    style={{ "--spine-a": "var(--thermal-2)", "--spine-b": "var(--thermal-4)", "--spine-c": "var(--thermal-6)" } as React.CSSProperties} 
  />
</div>
```

### C. Human-in-the-Loop Approval Queue
A high-contrast review gate presenting:
- Root cause diagnosis with numerical confidence
- Facility triage scores (travel time, dock congestion, cryogenic capacity, cost)
- Dual-action controls: Direct Operator Approval or Manual Override
- Audio-haptic click response and verified state feedback.

---

## 5. Accessibility & Motion Compliance

1. **Reduced Motion**: Full support for `prefers-reduced-motion: reduce`. All CSS transitions and animations collapse to instantaneous states (`0.01ms`) when enabled.
2. **Color Contrast**: All body text maintains minimum 4.5:1 contrast against `--surface-card`. Micro-labels maintain minimum 3:1 against background.
3. **Screen Readers**: All status indicators include explicit `aria-live` and `role="status"` properties.
