# ColdChain Rescue — Color System Specification

## Philosophy
The ColdChain Rescue color system is engineered for long-shift operations center legibility, zero ocular fatigue, and functional priority signaling. The interface avoids gratuitous multi-hue gradients, decorative glows, and bright background cards.

The map canvas and primary interface remain visually dominant in deep near-black and charcoal tones, allowing color to signify operational state rather than ornamentation.

---

## 1. Neutral Surfaces & Backgrounds

| Token | Hex Value | Usage |
|---|---|---|
| `--surface-canvas` | `#080A0F` | Global command center background, deep night map canvas |
| `--surface-subtle` | `#0E121A` | Secondary container surfaces, sidebars, header rails |
| `--surface-card` | `#141B26` | Floating telemetry inspectors, bottom sheets, modals |
| `--surface-elevated`| `#1C2433` | Hover states, active row selections, dropdown menus |
| `--border-subtle` | `#1E2638` | Structural 1px division lines |
| `--border-strong` | `#2D3A52` | Focused component outlines, keyboard nav rings |

---

## 2. Typographic Palette

| Token | Hex Value | Contrast Ratio | Usage |
|---|---|---|---|
| `--text-primary` | `#F1F5F9` | 15.8:1 | Primary telemetry numbers, headlines, active vehicle IDs |
| `--text-secondary`| `#94A3B8` | 7.2:1 | Section labels, status summaries, table headers |
| `--text-muted` | `#64748B` | 4.6:1 | Timestamp metadata, unit symbols (°C, km/h), secondary tags |
| `--text-dim` | `#334155` | 2.5:1 | Disabled controls, inactive route segments |

---

## 3. Functional Status & Severity Accents
Every accent color possesses a single unambiguous semantic meaning. No more than four functional colors are active concurrently.

### Emerald (`--status-nominal`)
- **Hex**: `#10B981` (500) / `#059669` (600)
- **Meaning**: Nominal temperature corridor (2.0°C – 8.0°C), healthy reefer compressor, verified AI recovery, approved route.

### Amber (`--status-warning`)
- **Hex**: `#F59E0B` (500) / `#D97706` (600)
- **Meaning**: Ambient heatwave exposure (>40°C outside), temperature trend drifting toward threshold (+0.25°C/min), moderate traffic congestion.

### Rose / Crimson (`--status-critical`)
- **Hex**: `#F43F5E` (500) / `#E11D48` (600)
- **Meaning**: Temperature breach (>8.0°C internal), compressor mechanical seizure, time-to-critical < 10m, emergency diversion required.

### Cyan (`--status-ai`)
- **Hex**: `#06B6D4` (500) / `#0891B2` (600)
- **Meaning**: AI agent operational loops, dynamic route calculation vectors, active telemetry sensors.

---

## 4. Anti-AI-Slop Governance
- **Strictly Prohibited**: Neon magenta gradients, multi-color rainbow charts, glowing button shadows with blur > 8px, purple AI cards.
- **Rule**: If a color does not indicate telemetry status, route direction, or interactive affordance, it must be removed.
