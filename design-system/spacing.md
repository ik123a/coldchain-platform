# ColdChain Rescue — Spacing & Layout Architecture

## Philosophy
ColdChain Rescue adheres to an 8-point spatial system with a 4-point sub-grid for high-density telematics widgets.

The product breathes: large map surfaces dominate the view (60–75%), while information is progressively revealed through floating contextual HUDs and bottom sheets rather than edge-to-edge widget crowding.

---

## 1. Grid Scale

| Token | Value | Pixel | Typical Use Case |
|---|---|---|---|
| `space-1` | 0.25rem | 4px | Internal badge padding, icon-to-label gaps |
| `space-2` | 0.5rem | 8px | Table row vertical padding, tight button spacing |
| `space-3` | 0.75rem | 12px | Card internal element separation, list spacing |
| `space-4` | 1.0rem | 16px | Standard card padding, toolbar spacing |
| `space-5` | 1.25rem | 20px | Floating HUD margins from viewport edges |
| `space-6` | 1.5rem | 24px | Major section padding, drawer margins |
| `space-8` | 2.0rem | 32px | Modal dialog internal padding |
| `space-12` | 3.0rem | 48px | Landing page hero vertical whitespace |

---

## 2. Radii & Elevation

| Token | Value | Usage |
|---|---|---|
| `--radius-sm` | 4px | Micro badges, status pills, code chips |
| `--radius-md` | 8px | Standard cards, interactive action buttons |
| `--radius-lg` | 12px | Floating telemetry inspector panels, modals |
| `--radius-xl` | 20px | Pull-up bottom sheets, drawer top corners |

### Elevation Shadows
- **Shadow Floating**: `0 8px 32px -4px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255, 255, 255, 0.08)`
- Avoid colored glowing shadows (`box-shadow: 0 0 20px rgba(0,255,255,0.8)`).
