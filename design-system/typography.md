# ColdChain Rescue — Typography Specification

## Philosophy
Typography in ColdChain Rescue prioritizes instant numerical scanability, tabular alignment, and editorial authority.

Fleet operators and logistics engineers must read temperatures, ETAs, and risk levels in fractions of a second under stressful operational conditions.

---

## 1. Typeface Selection

- **Primary UI Sans**: `Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `sans-serif`
  - High x-height, open apertures, excellent legibility at micro sizes (10px–12px).
- **Data & Telemetry Monospace**: `JetBrains Mono`, `ui-monospace`, `SFMono-Regular`, `Menlo`, `monospace`
  - Strict tabular numbers (`font-feature-settings: 'tnum' 1`), unambiguous zero vs O, consistent column alignment.

---

## 2. Type Scale & Hierarchy

| Role | Size | Weight | Line Height | Tracking | Font | Example Usage |
|---|---|---|---|---|---|---|
| **Display Hero** | 56px | 700 (Bold) | 1.05 | -0.03em | Sans | "Keep every shipment inside the safe zone." |
| **Section Headline** | 28px | 600 (Semibold) | 1.2 | -0.02em | Sans | "Live Fleet Operations" |
| **Metric Large** | 36px | 700 (Bold) | 1.1 | -0.02em | Mono | `41.8°C`, `00:07:42` |
| **Metric Medium** | 20px | 600 (Semibold) | 1.2 | -0.01em | Mono | `4.8°C`, `42 km/h` |
| **Body Primary** | 14px | 400 (Regular) | 1.5 | 0 | Sans | Operational summaries, agent reasoning text |
| **Body Secondary** | 13px | 400 (Regular) | 1.4 | 0 | Sans | Modal descriptions, table rows |
| **Label / Badge** | 11px | 600 (Semibold) | 1.0 | +0.06em | Sans/Mono | `TRUCK-104`, `CRITICAL`, `ETA 14m` |
| **Micro Metadata** | 10px | 500 (Medium) | 1.0 | +0.08em | Mono | `LAT: 28.5829`, `LNG: 77.1042` |

---

## 3. Strict Typographic Rules
1. **Never uppercase whole paragraphs**: All-caps is reserved exclusively for small micro-badges (<= 11px) and vehicle identifiers (`TRUCK-104`).
2. **Tabular Numerals**: All live telematics (temperatures, speeds, countdowns) MUST use `font-variant-numeric: tabular-nums` to eliminate jitter when digits increment.
3. **Restrained Weights**: Restrict to 400 (Regular), 500 (Medium), 600 (Semibold), 700 (Bold). Avoid hairline weights (100–200) and ultra-heavy black weights (900).
