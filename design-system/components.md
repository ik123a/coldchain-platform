# ColdChain Rescue — Component Specifications

## 1. Vehicle Marker System
- **Nominal State**: 18px discrete circle with 2px white stroke, solid emerald or cyan interior. Includes subtle directional pointer indicating heading angle (0–360°).
- **Warning State**: Solid amber interior with 1px outer ring.
- **Critical Breach**: Solid rose interior with gentle 2.0s pulse ring (opacity 0.7 -> 0.0, radius 18px -> 32px).
- **Clustering**: When zoomed out beyond level 11, vehicles condense into minimalist numeric badges (`12 Reefers`) without jitter.

---

## 2. Route Polylines
- **Active Route**: 3px solid cyan/blue path with 0.1 opacity outer shadow.
- **Traversed Route**: Muted solid gray (`#334155`).
- **Emergency Diversion Route**: High-contrast solid emerald (`#10B981`) branching cleanly at intersection nodes.
- **Traffic Congestion**: Segment overlay colored amber or rose with dashed pattern.

---

## 3. Floating Telemetry Inspector (Progressive Disclosure Level 1)
- Position: Anchored 24px above selected vehicle or pinned to top-right viewport.
- Dimensions: Max width 340px, padding 16px.
- Contents:
  - Header: Vehicle ID (`TRUCK-104`) + status badge (`NOMINAL` / `CRITICAL`)
  - Big Metric: Core Temperature (`4.8°C`) + target band (`2-8°C`)
  - Sub-metrics: Speed (`42 km/h`), Ambient (`41.8°C`), ETA (`14m`)
  - Action: "Open Full Telemetry Sheet" affordance.

---

## 4. Telemetry Bottom Sheet & Drawer (Progressive Disclosure Level 2)
- Mobile & Desktop progressive disclosure panel.
- Contents:
  - Temperature timeline chart (Inside vs Outside with Arrhenius degradation curve).
  - Subsystem health bars (Compressor, Battery, Tires, Brakes).
  - Driver metrics (Harsh braking, safety score).
  - AI Diagnostics feed (Live reasoning logs).

---

## 5. Autonomous AI Operations Panel
- Format: Chronological operational stream (Analyst tone).
- States:
  - `● Monitoring`: Evaluating sensor readings against spike/shift gates.
  - `● Diagnosis`: Compressor wear identified at 84%.
  - `● Prediction`: Estimated critical excursion in 7m 42s.
  - `● Facility Search`: Ranked cold-storage hubs by capacity & dock availability.
  - `● Recommendation`: Diversion to Hub Beta (ETA 9m, Risk HIGH -> MED).
- Controls: Primary action button "Approve Diversion", secondary "Inspect Alternatives".
